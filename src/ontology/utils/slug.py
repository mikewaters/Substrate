import re

DEFAULT_NAMESPACE_SPLIT = ":"


def make_namespace(prefix: str, title: str):
    return f"{prefix}{DEFAULT_NAMESPACE_SPLIT}{generate_slug(title)}"


def split_namespace(namespace: str):
    return namespace.split(DEFAULT_NAMESPACE_SPLIT, 1)


def generate_identifier(title: str, namespace: str = None) -> str:
    """Generate a URI identifier from a title.

    Args:
        title: Topic title
        namespace: parent' namespace (eg 'tx:taxonomy' should be "taxonomy")

    Returns:
        Generated identifier

    Example:
        >>> TopicRepository.generate_identifier("Hello World!", "Parent")
        'parent:hello-world'
    """
    # just in case, usually this is taken care of in the taxonomy
    namespace_slug = generate_slug(namespace)

    slug = generate_slug(title)

    return f"{namespace_slug}:{slug}"


def generate_slug(title: str) -> str:
    """Generate a URL-friendly slug from a title.

    Args:
        title: Topic title

    Returns:
        Generated slug

    Example:
        >>> TopicRepository.generate_slug("Hello World!")
        'hello-world'
    """
    # Convert to lowercase
    slug = title.lower()

    # Replace spaces and special characters with hyphens
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    return slug
