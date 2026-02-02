from enum import Enum
from functools import singledispatch

from llama_index.core import SimpleDirectoryReader

from catalog.ingest.directory import DirectorySource
from catalog.ingest.obsidian import ObsidianVaultSource, ObsidianVaultReader
from catalog.ingest.schemas import IngestDirectoryConfig, IngestObsidianConfig

__all__ = ["create_source", "create_reader"]

@singledispatch
def create_source(config):
    raise TypeError(f"Unsupported config type: {type(config)}")

@create_source.register
def _(config: IngestObsidianConfig):
    return ObsidianVaultSource(config.source_path, vault_schema=config.vault_schema)

@create_source.register
def _(config: IngestDirectoryConfig):
    return DirectorySource(
        config.source_path,
        patterns=config.patterns,
        encoding=config.encoding,
    )


@singledispatch
def create_reader(config):
    raise TypeError(f"Unsupported config type: {type(config)}")

@create_reader.register
def _(config: IngestObsidianConfig):
    return ObsidianVaultReader(config.source_path)

@create_reader.register
def _(config: IngestDirectoryConfig):
    return SimpleDirectoryReader(
        config.source_path,
        patterns=config.patterns,
        encoding=config.encoding,
    )




