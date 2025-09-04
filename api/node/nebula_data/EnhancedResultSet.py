from nebula3.data.ResultSet import ResultSet
from nebula3.data.DataObject import Node, Relationship, PathWrapper

from .EnhancedNode import EnhancedNode


class EnhancedResultSet(ResultSet):
    """增强版的ResultSet，添加as_dataframe方法"""
    def __init__(self, result_set):
        # 获取原始ResultSet的必要属性
        super().__init__(
            all_latency=getattr(result_set, '_all_latency', None),
            resp=getattr(result_set, '_resp', None),
            timezone_offset=getattr(result_set, '_timezone_offset', None)
        )
        # 复制原始结果集的所有属性
        self.__dict__.update(result_set.__dict__)

    def as_primitive(self):
        """Convert result set to list of dict with primitive values per row

        :return: list<dict>
        """
        return [
            {
                col_key: self.row_values(row_index)[col_index].cast_primitive()
                for col_index, col_key in enumerate(self.keys())
            }
            for row_index in range(self.row_size())
        ]

    def dict_for_vis(self):
        """Convert result set to a dictionary format suitable for visualization.

        Example:
        {
            'nodes': [
                {
                    'id': 'player100',
                    'labels': ['player'],
                    'props': {
                        'name': 'Tim Duncan',
                        'age': '42',
                        'id': 'player100'
                    }
                },
                {
                    'id': 'player101',
                    'labels': ['player'],
                    'props': {
                        'age': '36',
                        'name': 'Tony Parker',
                        'id': 'player101'
                    }
                }
            ],
            'edges': [
                {
                    'src': 'player100',
                    'dst': 'player101',
                    'name': 'follow',
                    'props': {
                        'degree': '95'
                    }
                }
            ],
            'nodes_dict': {
                'player100': {
                    'id': 'player100',
                    'labels': ['player'],
                    'props': {
                        'name': 'Tim Duncan',
                        'age': '42',
                        'id': 'player100'
                    }
                },
                'player101': {
                    'id': 'player101',
                    'labels': ['player'],
                    'props': {
                        'age': '36',
                        'name': 'Tony Parker',
                        'id': 'player101'
                    }
                }
            },
            'edges_dict': {
                "('player100', 'player101', 0, 'follow')": {
                    'src': 'player100',
                    'dst': 'player101',
                    'name': 'follow',
                    'props': {
                        'degree': '95'
                    }
                }
            },
            'nodes_count': 2,
            'edges_count': 1
        }

        :return: dict with keys:
            nodes, edges, nodes_dict, edges_dict, nodes_count, edges_count
        """

        def add_to_nodes_or_edges(nodes_dict, edges_dict, item):
            if isinstance(item, Node):
                node_id = str(item.get_id().cast())
                tags = item.tags()  # list of strings
                props_raw = dict()
                for tag in tags:
                    # TODO: handle duplicate keys among tags
                    props_raw.update(item.properties(tag))
                props = {
                    k: str(v.cast()) if hasattr(v, "cast") else str(v)
                    for k, v in props_raw.items()
                }

                if "id" not in props:
                    props["id"] = node_id

                if node_id not in nodes_dict:
                    nodes_dict[node_id] = {
                        "id": node_id,
                        "labels": tags,
                        "props": props,
                    }
                else:
                    nodes_dict[node_id]["labels"] = list(
                        set(nodes_dict[node_id]["labels"] + tags)
                    )
                    nodes_dict[node_id]["props"].update(props)

            elif isinstance(item, Relationship):
                src_id = str(item.start_vertex_id().cast())
                dst_id = str(item.end_vertex_id().cast())
                rank = item.ranking()
                edge_name = item.edge_name()
                props_raw = item.properties()
                props = {
                    k: str(v.cast()) if hasattr(v, "cast") else str(v)
                    for k, v in props_raw.items()
                }
                if str((src_id, dst_id, rank, edge_name)) not in edges_dict:
                    edges_dict[str((src_id, dst_id, rank, edge_name))] = {
                        "src": src_id,
                        "dst": dst_id,
                        "name": edge_name,
                        "rank": rank,
                        "props": props,
                    }
                else:
                    edges_dict[str((src_id, dst_id, rank, edge_name))]["props"].update(
                        props
                    )

            elif isinstance(item, PathWrapper):
                for node in item.nodes():
                    add_to_nodes_or_edges(nodes_dict, edges_dict, node)
                for edge in item.relationships():
                    add_to_nodes_or_edges(nodes_dict, edges_dict, edge)

            elif isinstance(item, list):
                for it in item:
                    add_to_nodes_or_edges(nodes_dict, edges_dict, it)

        nodes_dict = dict()
        edges_dict = dict()

        columns = self.keys()
        for col_num in range(self.col_size()):
            col_name = columns[col_num]
            col_list = self.column_values(col_name)
            add_to_nodes_or_edges(nodes_dict, edges_dict, [x.cast() for x in col_list])
        nodes = list(nodes_dict.values())
        edges = list(edges_dict.values())
        # move rank to props, omit rank 0
        for edge in edges:
            if "rank" in edge:
                rank = edge.pop("rank")
                if rank != 0:
                    edge["props"]["rank"] = rank

        return {
            "nodes": nodes,
            "edges": edges,
            "nodes_dict": nodes_dict,
            "edges_dict": edges_dict,
            "nodes_count": len(nodes),
            "edges_count": len(edges),
        }

    def as_data_frame(self, primitive: bool = True):
        """Convert result set to a DataFrame.

        :param primitive: if True, convert all values to primitive types
        :return: DataFrame
        """
        # TODO: support polars df
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is not installed")

        if self.is_empty():
            return pd.DataFrame()

        data = dict()
        for col in self.keys():
            if primitive:
                data[col] = [EnhancedNode(x).cast_primitive() for x in self.column_values(col)]
            else:
                data[col] = [x.cast() for x in self.column_values(col)]

        return pd.DataFrame(data)
