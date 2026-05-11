
import json
import os
import logging
from typing import List, Dict

logger = logging.getLogger("knowledge_graph")


class KnowledgeGraphLite:
    """
    Zero-Dependency Knowledge Graph using Adjacency List (Dict).
    Stores relationships: Subject -> Predicate -> Object
    """
    def __init__(self):
        self.file_path = "brain/data/knowledge_graph.json"
        self.graph = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f: return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load knowledge graph: {e}")
        return {"nodes": [], "edges": []}

    def _save(self):
        try:
            with open(self.file_path, 'w') as f: json.dump(self.graph, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge graph: {e}")

    def add_relation(self, subject: str, predicate: str, object_: str):
        """Adds a triple: ('Python', 'is_good_for', 'AI')"""
        # Add nodes if missing
        if subject not in self.graph["nodes"]: self.graph["nodes"].append(subject)
        if object_ not in self.graph["nodes"]: self.graph["nodes"].append(object_)
        
        # Add edge
        edge = {"source": subject, "rel": predicate, "target": object_}
        if edge not in self.graph["edges"]:
            self.graph["edges"].append(edge)
            self._save()

    def get_related(self, entity: str) -> List[str]:
        """Finds all concepts related to an entity."""
        related = []
        for edge in self.graph["edges"]:
            if edge["source"].lower() == entity.lower():
                related.append(f"{edge['rel']} -> {edge['target']}")
            elif edge["target"].lower() == entity.lower():
                related.append(f"Is {edge['rel']} of -> {edge['source']}")
        return related

kg_lite = KnowledgeGraphLite()
