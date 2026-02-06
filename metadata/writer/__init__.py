from metadata.writer.registry import register
from metadata.writer.fb2 import FB2MetadataWriter
from metadata.writer.epub import EPUBMetadataWriter

register(FB2MetadataWriter())
register(EPUBMetadataWriter())
