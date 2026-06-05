from app.metadata.writer.registry import register
from app.metadata.writer.fb2 import FB2MetadataWriter
from app.metadata.writer.epub import EPUBMetadataWriter

register(FB2MetadataWriter())
register(EPUBMetadataWriter())
