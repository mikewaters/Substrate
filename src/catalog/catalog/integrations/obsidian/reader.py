"""Obsidian vault source reader.

Provides source reading capabilities for Obsidian vaults,
extracting markdown files with YAML frontmatter parsing.

Architecture decisions:
1. Build on SimpleDirectoryReader for filesystem traversal
2. Build on MarkdownReader for basic markdown parsing
3. Follow the interface and behavior of the existing ObsidianReader impl
4. Frontmatter extraction is performed at the Reader level, not in a custm Extractor;
    while frontmatter is within document content, it is really document-level metadata
    and should be extracted as early as possible for indexing and filtering.
    Furthermore, Extractors are designed to work on arbitrary nodes, and a frontmatter
    extractor would only work on complete non-split Markdown documents.

Learnings:
1. (LLamaindex Caching) Its critical for a Reader to be deterministic. Some python behavior results in non-determinism,
like list order. If the reader doesnt return the same content plus metadata, pipelines will not
cache between runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple, Union

import yaml
from agentlayer.logging import get_logger
from fsspec import AbstractFileSystem
from llama_index.core import Document
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.readers.file import MarkdownReader

logger = get_logger(__name__)


import re
from typing import List, Any, Dict, Optional
from llama_index.core.schema import TransformComponent

# from llama_index.legacy.node_parser.relational.markdown_element import (
#     MarkdownElementNodeParser,
# )

# ---------------------------
# 1) Obsidian-aware cleanup
# ---------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]")
_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_CALLOUT_RE = re.compile(r"^>\s*\[!(\w+)\](?:\+|-)?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n.*?\n---\s*\n", re.DOTALL)


def _strip_frontmatter(md: str) -> str:
    # Generic: removes YAML frontmatter; optionally parse it into metadata in a richer version.
    return re.sub(_FRONTMATTER_RE, "", md, count=1)


def _replace_wikilinks(md: str) -> str:
    # [[Note]] -> Note
    # [[Note|Display]] -> Display
    def repl(m: re.Match) -> str:
        target = (m.group(1) or "").strip()
        display = (m.group(2) or "").strip()
        return display if display else target

    return re.sub(_WIKILINK_RE, repl, md)


def _replace_embeds(md: str) -> str:
    # ![[Target]] -> (Embedded: Target)
    # If you can resolve embeds at ingest time, inline them here instead of a placeholder.
    def repl(m: re.Match) -> str:
        target = (m.group(1) or "").strip()
        return f"(Embedded: {target})"

    return re.sub(_EMBED_RE, repl, md)


def _normalize_callouts(md: str) -> str:
    # > [!note] Title -> Callout (note): Title
    # Leaves the quoted body lines intact, which is usually fine for embeddings.
    def repl(m: re.Match) -> str:
        kind = (m.group(1) or "").lower()
        title = (m.group(2) or "").strip()
        title_part = f" — {title}" if title else ""
        return f"Callout ({kind}){title_part}"

    return re.sub(_CALLOUT_RE, repl, md)


def _collapse_blank_lines(md: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", md).strip()


class ObsidianMarkdownNormalize(TransformComponent):
    """
    Generic Obsidian markdown normalizer.

    This runs BEFORE node parsing so MarkdownNodeParser / MarkdownElementNodeParser
    see cleaner markdown.
    """

    def __call__(self, nodes: List[Any], **kwargs: Any) -> List[Any]:
        for node in nodes:
            text = getattr(node, "text", None)
            if not isinstance(text, str) or not text.strip():
                continue

            cleaned = text
            cleaned = _strip_frontmatter(cleaned)
            cleaned = _replace_embeds(cleaned)
            cleaned = _replace_wikilinks(cleaned)
            cleaned = _normalize_callouts(cleaned)
            cleaned = _collapse_blank_lines(cleaned)

            node.text = cleaned
        return nodes

# Compile once at module scope
# - Allows optional BOM at start
# - Requires opening fence on its own line
# - Captures until a closing fence on its own line (--- or ...)
# - Closing fence must be followed by newline or end-of-string
_FRONTMATTER_RE = re.compile(
    r"\A(?:\ufeff)?---[ \t]*\r?\n"          # opening fence
    r"(?P<yaml>.*?)"                        # yaml body (non-greedy)
    r"\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)",  # closing fence
    re.DOTALL,
)

def parse_frontmatter(
    content: str,
    *,
    max_scan_chars: int = 65536,
    on_yaml_error: str = "none",  # "none" or "raise"
) -> Tuple[Optional[dict[str, Any]], str]:
    """
    Extract YAML frontmatter if present at the very start of the document.
    Returns (frontmatter_dict_or_none, remaining_content).
    """

    # Limit scan to reduce worst-case regex work on huge files.
    head = content[:max_scan_chars]
    m = _FRONTMATTER_RE.match(head)
    if not m:
        return None, content

    yaml_text = m.group("yaml")
    remaining = content[m.end():]  # use original content indices

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        if on_yaml_error == "raise":
            raise
        # lenient: treat as no frontmatter; keep content unchanged
        return None, content

    if data is None:
        return {}, remaining
    if isinstance(data, dict):
        return data, remaining

    # Policy: non-mapping YAML is unusual; preserve it but make it explicit
    return {"_raw": data}, remaining



class ObsidianMarkdownReader(MarkdownReader):
    def __init__(
        self,
        extract_frontmatter: bool = True,
        remove_frontmatter_from_text: bool = True,
        frontmatter_metadata_key: str = "frontmatter",  # or "obsidian_frontmatter"
        split_on_headers: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._extract_frontmatter = extract_frontmatter
        self._remove_frontmatter_from_text = remove_frontmatter_from_text
        self._frontmatter_metadata_key = frontmatter_metadata_key
        self._split_on_headers = split_on_headers
        super().__init__(*args, **kwargs)

    def _read_text(self, file: Any, fs: Optional[AbstractFileSystem]) -> str:
        # mirror MarkdownReader behavior as closely as possible
        if fs is not None:
            with fs.open(file, "r") as f:
                return f.read()
        with open(file, "r") as f:
            return f.read()

    def load_data(
        self,
        file: Any,  # Path | str
        extra_info: Optional[dict[str, Any]] = None,
        fs: Optional[AbstractFileSystem] = None,
    ) -> List[Document]:
        extra_info = dict(extra_info or {})
        content = self._read_text(file, fs)
        extracted = False
        # Preserve upstream MarkdownReader behavior: hyperlink/image removal happens
        # in parse_tups today, so apply it here before splitting.
        # (You can also call super().parse_tups after you refactor, but then
        # you'd lose access to raw content for frontmatter unless you re-read.)
        if self._remove_hyperlinks:
            content = self.remove_hyperlinks(content)
        if self._remove_images:
            content = self.remove_images(content)

        if self._extract_frontmatter:
            try:
                frontmatter, remainder = parse_frontmatter(content)
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter YAML in {file}: {e}")
            else:
                # only treat it as frontmatter if parse_frontmatter actually found one
                if frontmatter is not None:
                    extra_info[self._frontmatter_metadata_key] = frontmatter
                    if self._remove_frontmatter_from_text:
                        content = remainder
                    extracted = True
        # Now do the normal header splitting and document creation
        if not self._split_on_headers:
            doc = Document(text=content, metadata=extra_info)
            if extracted:
                doc.excluded_embed_metadata_keys = [self._frontmatter_metadata_key]
                doc.excluded_llm_metadata_keys = [self._frontmatter_metadata_key]
            return [doc]
        else:
            tups = self.markdown_to_tups(content)
            results = []
            for header, text in tups:
                if header is None:
                    doc = Document(text=text, metadata=extra_info)
                else:
                    doc = Document(text=f"\n\n{header}\n{text}", metadata=extra_info)
                if extracted:
                    doc.excluded_embed_metadata_keys = [self._frontmatter_metadata_key]
                    doc.excluded_llm_metadata_keys = [self._frontmatter_metadata_key]
                results.append(doc)
            return results


def is_hardlink(filepath: Path) -> bool:
    """
    Check if a file is a hardlink by checking the number of links to/from it.

    Args:
        filepath: Path to the file.

    Returns:
        True if the file has more than one hard link.
    """
    stat_info = os.stat(filepath)
    return stat_info.st_nlink > 1


def extract_tasks(text: str, should_remove_tasks: bool) -> Tuple[List[str], str]:
    """
    Extract markdown tasks from text.

    A task is a checklist item in markdown, for example:
        - [ ] Do something
        - [x] Completed task

    Args:
        text: Document text to extract tasks from.

    Returns:
        Tuple of (list of task strings, text with task lines removed).
    """
    # Matches lines starting with '-' or '*' followed by a checkbox.
    task_pattern = re.compile(
        r"^\s*[-*]\s*\[\s*(?:x|X| )\s*\]\s*(.*)$", re.MULTILINE
    )
    tasks = task_pattern.findall(text)
    cleaned_text = task_pattern.sub("", text) if should_remove_tasks else text
    return tasks, cleaned_text


def extract_wikilinks(text: str) -> List[str]:
    """
    Extract Obsidian wikilinks from text.

    Matches patterns like:
        - [[Note Name]]
        - [[Note Name|Alias]]

    Args:
        text: Document text to extract wikilinks from.

    Returns:
        List of unique wikilink targets (aliases are stripped).
    """
    pattern = r"\[\[([^\]]+)\]\]"
    matches = re.findall(pattern, text)
    links: List[str] = []
    seen: set[str] = set()
    for match in matches:
        # If a pipe is present (e.g. [[Note|Alias]]), take only the part before it.
        target = match.split("|")[0].strip()
        if target in seen:
            continue
        links.append(target)
        seen.add(target)
    return links


class ObsidianVaultReader(SimpleDirectoryReader):
    """
    Obsidian vault reader built on SimpleDirectoryReader.
    Should support all features of ObsidianReader, but with
    additional features:
    - Supports llamaindex docstore/storagecontext persistence
    - Extracts frontmatter and other enrichments

    This reader walks an Obsidian vault, loads markdown files using MarkdownReader,
    and enriches documents with Obsidian-specific metadata including wikilinks
    and backlinks.

    Metadata extraction: We could use a llama.Extractor - in the
    ingestion pipeline - but that would require a full pipeline run
    and so be unusable at the Document level.

    Args:
        input_dir: Path to the Obsidian vault.
        extract_tasks: If True, extract tasks from the text and store them in metadata.
        remove_tasks_from_text: If True and extract_tasks is True, remove task lines
            from the main document text.
        exclude_hidden: Must be True (default). Non-hidden traversal is not supported.
        **kwargs: Additional arguments passed to SimpleDirectoryReader (except
            required_exts and file_extractor which are overridden).

    Raises:
        NotImplementedError: If exclude_hidden=False or non-local filesystem is used.
    """

    def __init__(
        self,
        input_dir: Optional[Union[Path, str]] = None,
        input_files: Optional[list] = None,
        extract_frontmatter: bool = True, # pull Document metadata from YAML frontmatter
        remove_frontmatter_from_text: bool = True, # strip frontmatter out of doc content if it was extracted
        extract_wikilinks: bool = True, # whether to extract wikilinks and backlinks
        remove_dead_wikilinks: bool = False, # you do not want this if using `LinkResolutionTransform`
        vault_metadata: dict[str, Any] | None = None, # extra metadata to add to each doc
        # for compat with upstream `ObsidianReader`
        extract_tasks: bool = False,
        remove_tasks_from_text: bool = False,
        split_on_headers: bool = False, # Whether to chunk or not; upstream default is True
        **kwargs: Any,
    ) -> None:

        # Input checks
        if "exclude_hidden" in kwargs and not kwargs["exclude_hidden"]:
            raise NotImplementedError(
                "SimpleObsidianReader only supports exclude_hidden=True."
            )

        # Check for non-local filesystem (fsspec)
        if "fs" in kwargs and kwargs["fs"] is not None:
            raise NotImplementedError(
                "SimpleObsidianReader only supports local filesystems. "
                "Non-local sources via fsspec are not supported."
            )

        # Force markdown-only and use MarkdownReader
        kwargs.pop("required_exts", None)
        kwargs.pop("file_extractor", None)

        self._vault_root = input_dir.resolve()

        #TODO: Should the extractions just get moved down into the MarkdownReader?
        # Or moved up into the VaultReader load_data()?
        # Seems architecturally weird to have these split:
        # MarkdownReader does:
        # - frontmatter extraction
        # - removes images/hyperlinks
        # VaultReader does:
        # - wikilink extraction and backlink building
        # - task extraction
        #
        self._should_extract_tasks = extract_tasks
        self._should_remove_tasks = remove_tasks_from_text
        self._should_extract_links = extract_wikilinks
        self._remove_dead_wikilinks = remove_dead_wikilinks
        self._vault_metadata = vault_metadata or {}
        self._vault_metadata.update(self._get_vault_metadata())

        extractor = ObsidianMarkdownReader(
            extract_frontmatter=extract_frontmatter,
            remove_frontmatter_from_text=remove_frontmatter_from_text,
            split_on_headers=split_on_headers,
            remove_hyperlinks=False,  # keep links for wikilink extraction
            remove_images=True,      # keep images for wikilink extraction
        )

        super().__init__(
            input_dir=input_dir,
            input_files=input_files,
            required_exts=[".md"],  # Markdown files only
            exclude_hidden=True,  # Exclude .obsidian and hidden files
            exclude_empty=False,  # An empty .md file in Obsidian still has a title
            recursive=True,  # Walk subdirectories
            file_extractor={".md": extractor},
            file_metadata=self.get_file_metadata,  # Build Obsidian metadata
            # stable doc IDs are required for caching; if you have a vault that
            # moves around the filesystem, this will not correctly identify files.
            filename_as_id=True,
            raise_on_error=False, # YOLO
            **kwargs,
        )

    def _get_vault_metadata(self) -> dict[str, Any]:
        """
        Get static vault-level metadata to include in each document.

        Returns:
            Dictionary of vault-level metadata.
        """
        metadata = {}
        return metadata

    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Generate Obsidian-specific metadata for a file.
        Passed into superclass as a callback function, which is
        executed in `SimpleDirectoryReader.load_file` (which is
        itself called from `SimpleDirectoryReader.load_data`).

        Includes both Obsidian-specific fields and standard file metadata
        that SimpleDirectoryReader normally provides.

        Metadata which requires reading the file isnt available here,
        given the file_extractor has not run yet; for this, see
        `ObsidianMarkdownReader`.

        Obsidian metadata captured:
        - file_name: basename of the vault file
        - note_name: basename of the vault file without extension
        - folder_path: location of the note in the vault
        - folder_name: name of the folder the note is in (leaf)

        Basic metadata captured:
        - file_type: "text/markdown"
        - full path, mtime and ctime etc

        Args:
            file_path: Path to the markdown file.

        Returns:
            Dictionary containing file metadata for caching and Obsidian features.
        """
        metadata = {}

        file_path_obj = Path(file_path).resolve()
        metadata['file_name'] = file_path_obj.name
        metadata['folder_path'] = str(file_path_obj.parent)
        metadata['note_name'] = file_path_obj.stem

        try:
            folder_name = str(file_path_obj.parent.relative_to(self._vault_root))
            if folder_name == ".":
                folder_name = ""
        except ValueError:
            # Fallback if relative_to fails
            folder_name = str(file_path_obj.parent)

        metadata['folder_name'] = folder_name
        metadata['file_type'] = "text/markdown"
        metadata['_format'] = "Markdown"
        metadata['_media_type'] = "text/markdown"

        # Add relative_path for PersistenceTransform compatibility
        try:
            metadata['relative_path'] = str(file_path_obj.relative_to(self._vault_root))
        except ValueError:
            # Fallback to filename if not within vault
            metadata['relative_path'] = file_path_obj.name


        # use superclass to get normal file metadata
        metadata.update(self.get_resource_info(str(file_path_obj)))

        return metadata

    def _is_safe_file(self, file_path: Path) -> bool:
        """
        Check if a file passes safety checks (not a hardlink, within vault).

        Args:
            file_path: Path to check.

        Returns:
            True if the file is safe to process.
        """
        resolved_path = file_path.resolve()

        # Check for hardlinks
        try:
            if is_hardlink(resolved_path):
                print(
                    f"Warning: Skipping file because it is a hardlink "
                    f"(potential malicious exploit): {file_path}"
                )
                return False
        except OSError as e:
            print(f"Warning: Could not check hardlink status for {file_path}: {e}")
            return False

        # Check path containment
        try:
            resolved_path.relative_to(self._vault_root)
        except ValueError:
            print(f"Warning: Skipping file outside input directory: {file_path}")
            return False

        return True

    def _extract_links(self, text: str) -> List[str]:
        """Extract link targets from document text.

        Override in subclasses to support different link formats
        (e.g. Heptabase markdown links instead of wikilinks).

        Args:
            text: Document text to extract links from.

        Returns:
            List of unique link target names.
        """
        return extract_wikilinks(text)

    def load_data(
        self,
        show_progress: bool = False,
        num_workers: Optional[int] = None,
        **load_kwargs: Any,
    ) -> List[Document]:
        """
        Load documents from the Obsidian vault with full metadata enrichment.

        This method:
        1. Filters files through safety checks (hardlink, path containment)
        2. Loads markdown files via SimpleDirectoryReader
        3. Extracts wikilinks and builds backlinks graph
        4. Optionally extracts tasks

        Args:
            show_progress: If True, show a progress bar.
            num_workers: Number of workers for parallel loading.
            **load_kwargs: Additional arguments.

        Returns:
            List of Document objects with Obsidian metadata.
        """
        # Filter input files through safety checks before loading
        # Dont do this for explicit `input_files`, assume the caller knows best
        safe_files = []
        for file_path in self.input_files:
            if self._is_safe_file(file_path):
                safe_files.append(file_path)

        # Update input_files to only include safe files
        self.input_files = safe_files

        # Load documents using parent class
        docs = super().load_data(
            show_progress=show_progress,
            num_workers=num_workers,
            **load_kwargs,
        )

        # Collect all valid note names (targets) to validate links against
        valid_notes = {
            doc.metadata.get("note_name")
            for doc in docs
            if doc.metadata.get("note_name")
        }

        # Build backlinks map: {target_note: [source_note1, source_note2, ...]}
        backlinks_map: Dict[str, set[str]] = {}

        # First pass
        for i, doc in enumerate(docs):
            note_name = doc.metadata.get("note_name", "")

            # Optionally extract wikilinks and build backlinks map
            if self._should_extract_links:
                raw_wikilinks = self._extract_links(doc.text)

                final_wikilinks = raw_wikilinks
                if self._remove_dead_wikilinks:
                    # Filter dead links
                    valid_wikilinks = []
                    for link in raw_wikilinks:
                        if link in valid_notes:
                            valid_wikilinks.append(link)
                        else:
                            current_file = doc.metadata.get("file_name", "unknown")
                            logger.debug(
                                f"Dead wikilink found in '{current_file}': [[{link}]]"
                            )
                    final_wikilinks = valid_wikilinks

                doc.metadata["wikilinks"] = final_wikilinks

                for link in final_wikilinks:
                    backlinks_map.setdefault(link, set()).add(note_name)

            # Optionally extract tasks
            if self._should_extract_tasks:
                tasks, cleaned_text = extract_tasks(doc.text, self._should_remove_tasks)
                doc.metadata["tasks"] = tasks
                if self._should_remove_tasks:
                    docs[i] = Document(text=cleaned_text, metadata=doc.metadata)

        # Second pass: assign backlinks
        if self._should_extract_links:
            for doc in docs:
                note_name = doc.metadata.get("note_name", "")
                doc.metadata["backlinks"] = sorted(
                    backlinks_map.get(note_name, set())
                )

        return docs

