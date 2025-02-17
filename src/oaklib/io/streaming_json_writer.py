import json
from dataclasses import dataclass
from typing import Any, Union

from linkml_runtime import CurieNamespace
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.utils.yamlutils import YAMLRoot

from oaklib.interfaces.obograph_interface import OboGraphInterface
from oaklib.io.streaming_writer import StreamingWriter
from oaklib.types import CURIE


def _keyval(x: Any) -> str:
    if isinstance(x, CurieNamespace):
        return str(x.curie())
    # if isinstance(x, EnumDefinitionImpl):
    #    if x.curie:
    #        return str(x.curie)
    return str(x)


@dataclass
class StreamingJsonWriter(StreamingWriter):
    """
    A writer that emits one document at a time in one stream

    """

    def emit(self, obj: Union[YAMLRoot, dict], label_fields=None):
        if isinstance(obj, dict):
            self.file.write(json.dumps(obj))
        else:
            oi = self.ontology_interface
            if isinstance(oi, OboGraphInterface):
                node = oi.node(obj, include_metadata=True)
                self.line(json_dumper.dumps(node))
            # self.file.write(json_dumper.dumps(obj))
        self.file.write("\n")

    def emit_curie(self, curie: CURIE, label=None):
        raise NotImplementedError
