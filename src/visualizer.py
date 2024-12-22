from src.binding.strategy import BindingStrategy
from src.binding.import_strategy import ImportStrategy

import os.path

import networkx as nx
import matplotlib.pyplot as plt


def visualize_project(binder: BindingStrategy):
    graph = nx.DiGraph()

    file_graph = binder.graph()
    for source_file in file_graph.source_files:
        graph.add_node(f"Source: {source_file.name}", type="source")

    for test in file_graph.test_files:
        test_node = f"Test: {test.name}"
        graph.add_node(test_node, type="test")

        for source_file in file_graph.links[test]:
            source_node = f"Source: {source_file.name}"
            graph.add_edge(test_node, source_node)

    pos = nx.spring_layout(graph)
    plt.figure(figsize=(12, 8))

    test_nodes = [
        node for node, data in graph.nodes(data=True) if data["type"] == "test"
    ]
    source_nodes = [
        node for node, data in graph.nodes(data=True) if data["type"] == "source"
    ]

    nx.draw_networkx_nodes(
        graph, pos, nodelist=test_nodes, node_color="red", label="Test Files"
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=source_nodes, node_color="blue", label="Source Files"
    )
    nx.draw_networkx_edges(graph, pos)
    nx.draw_networkx_labels(graph, pos, font_size=10, font_color="black")

    plt.legend()
    plt.title("Test-to-Source Links")
    plt.show()


if __name__ == "__main__":
    path = os.path.abspath(input("Enter the path to the project: "))
    binder = ImportStrategy(path)
    visualize_project(binder)
