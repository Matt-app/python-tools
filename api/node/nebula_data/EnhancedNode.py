from nebula3.data.DataObject import Node
from typing import Any

from nebula3.common.ttypes import (
    Geography,
    Value,
    Vertex,
    Edge,
    NullType,
    DateTime,
    Time,
)


class EnhancedNode(Node):
    def __init__(self):
        super().__init__(getattr(Node, '_value', None))

    def cast_primitive(self) -> Any:
        """
        automatically convert value wrapper to primitive type by calling casting method.

        : return: Any type (e.g. int, float, str, bool)
        """

        def _cast_node(node: Vertex):
            return {
                "vid": node.get_id().cast(),
                "tags": {
                    tag_name: {
                        k: v.cast_primitive()
                        for k, v in node.properties(tag_name).items()
                    }
                    for tag_name in node.tags()
                },
            }

        def _cast_relationship(edge: Edge):
            return {
                "src": edge.start_vertex_id().cast(),
                "dst": edge.end_vertex_id().cast(),
                "type": edge.edge_name(),
                "rank": edge.ranking(),
                "props": {k: v.cast_primitive() for k, v in edge.properties().items()},
            }

        def _cast_primitive(raw_value):
            _type = raw_value._value.getType()
            if _type == Value.__EMPTY__:
                return None
            elif _type == Value.NVAL:
                return None
            elif _type == Value.BVAL:
                return raw_value.as_bool()
            elif _type == Value.IVAL:
                return raw_value.as_int()
            elif _type == Value.FVAL:
                return raw_value.as_double()
            elif _type == Value.SVAL:
                return raw_value.as_string()
            elif _type == Value.LVAL:
                return [_cast_primitive(x) for x in raw_value.as_list()]
            elif _type == Value.UVAL:
                return {_cast_primitive(x) for x in raw_value.as_set()}
            elif _type == Value.MVAL:
                return {k: _cast_primitive(v) for k, v in raw_value.as_map().items()}
            elif _type == Value.TVAL:
                return raw_value.as_time().get_local_time_str()
            elif _type == Value.DVAL:
                return raw_value.as_date().__repr__()
            elif _type == Value.DTVAL:
                return raw_value.as_datetime().get_local_datetime_str()
            elif _type == Value.VVAL:
                return _cast_node(raw_value.as_node())
            elif _type == Value.EVAL:
                return _cast_relationship(raw_value.as_relationship())
            elif _type == Value.PVAL:
                path = raw_value.as_path()
                return {
                    "path_str": path.__repr__(),
                    "start_node": _cast_node(path.start_node()),
                    "edges": [_cast_relationship(x) for x in path.relationships()],
                    "nodes": [_cast_node(x) for x in path.nodes()],
                }
            elif _type == Value.GGVAL:
                return raw_value.as_geography().__repr__()
            elif _type == Value.DUVAL:
                return raw_value.as_duration().__repr__()
            else:
                raise RuntimeError(
                    "Unsupported type:{} to cast primitive".format(
                        raw_value._get_type_name()
                    )
                )

        return _cast_primitive(self)
