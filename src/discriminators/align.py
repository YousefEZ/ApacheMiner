from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Iterator, Optional, Self

from src.discriminators.file_types import FileChanges


@dataclass(frozen=True)
class CommitNode:
    hash: str
    changes: list[FileChanges]
    parents: list[Self]


@dataclass(frozen=True)
class Branch:
    head: CommitNode
    tail: CommitNode

    @cached_property
    def commits(self) -> set[str]:
        node = self.tail
        commits = {self.head.hash}
        while node.hash != self.head.hash:
            commits.add(node.hash)
            node = node.parents[0]
        return commits


class CommitAligner:
    """
    Inlines the branches into the main branch, so that the main branch
    contains all the changes from the other branches. This is done by
    tracing the path back to the main branch and then stitching the branch
    into the main branch. So that the main branch has no branches and all
    commits are ordered in terms of when they were commited into the main
    branch

    Example:

               F-------->G-------->H
               ^                   |
               |                   |
        B----->C----->D---->E      |
        ^                   |      |
        |                   v      v
        W-------->X-------->Y----->Z


        becomes W-->X-->B-->C-->D-->E-->Y-->F-->G-->H-->Z
    """

    def __init__(self, changes: list[tuple[str, list[FileChanges]]]):
        # TODO: restructure such that init doesn't contain logic
        self._changes = changes
        self._main_branch = self._make_main_branch(self._changes)
        self._inline_branches()
        tail = self._main_branch.tail
        while tail.parents:
            assert len(tail.parents) == 1
            tail = tail.parents[0]
        assert tail == self._main_branch.head

    def get_successor(self, node: CommitNode) -> Optional[CommitNode]:
        current_node = self._main_branch.tail
        successor = None
        while current_node.hash != node.hash:
            successor = current_node
            current_node = current_node.parents[0]
        return successor

    def _create_commit_from_changes(
        self, commit_hash: str, nodes: dict[str, CommitNode]
    ) -> CommitNode:
        """Finds the commit in the commits list

        Args:
            commits (list[tuple[str, list[FileChanges]]]): The commits to search
            hash (str): The hash of the commit to find

        Returns (tuple[str, list[FileChanges]]): The commit found
        """
        if commit_hash in nodes:
            return nodes[commit_hash]

        for idx in range(len(self._changes)):
            commit_hash, changes = self._changes[idx]

            if commit_hash != commit_hash:
                continue

            parents_hash = changes[0]["parents"].split("|")
            if changes[0]["parents"]:
                for parent_hash in parents_hash:
                    if parent_hash not in nodes:
                        self._create_commit_from_changes(parent_hash, nodes)
            parents = (
                [nodes[parent] for parent in parents_hash]
                if changes[0]["parents"]
                else []
            )

            nodes[commit_hash] = CommitNode(commit_hash, changes, parents)
            return nodes[commit_hash]

        raise ValueError(f"Commit with hash {hash} not found")

    def _make_main_branch(self, commits: list[tuple[str, list[FileChanges]]]) -> Branch:
        """Creates a branch from the commits given, assuming all the commits
        eventually lead to the commit containing 0 parents to the last commit that
        contains no children

        Args:
            commits (list[tuple[str, list[FileChanges]]]): The commits to create
                    the branch from

        Returns (Branch): The branch created from the commits given
        """
        nodes: dict[str, CommitNode] = dict()

        for idx in range(len(commits)):
            commit_hash, commit = commits[idx]
            changes: list[FileChanges] = list(commit)
            parents = (
                [
                    (
                        nodes[parent]
                        if parent in nodes
                        else self._create_commit_from_changes(parent, nodes)
                    )
                    for parent in changes[0]["parents"].split("|")
                ]
                if changes[0]["parents"]
                else []
            )
            nodes[commit_hash] = CommitNode(
                hash=commit_hash, changes=changes, parents=parents
            )

        assert (
            nodes[commits[0][0]].parents == []
        ), "The first commit should have no parents"

        return Branch(head=nodes[commits[0][0]], tail=nodes[commits[-1][0]])

    def _trace_path_back_to_main(self, tail: CommitNode) -> Branch:
        """Traces the path back to the main branch

        Args:
            tail (CommitNode): The tail of the branch to trace back to main

        Returns (Branch): The branch that was traced back to main

        Example:

            B----->C----->D---->E
            ^                   |
            |                   v
            W-------->X-------->Y----->Z

            Where E is the arg tail then the result is a branch with the head
            at B and the tail at E
        """
        node = tail
        while node.parents[0].hash not in self._main_branch.commits:
            node = node.parents[0]
        return Branch(node, tail)

    def _stitch_path(self, node: CommitNode, path: Branch, visited: set[str]) -> Branch:
        """Stitches the branch into the node given. It does this by finding the
        earliest node in the branch that is not in the visited, and treats it as the
        start of the branch

        Args:
            node (CommitNode): The node to stitch the branch into
            path (Branch): The branch to stitch into the node
            visited (set[str]): The set of already visited nodes

        Returns (Branch): an instance that contains the start of the stitched path and
            the tail of that path being the node.

        Example:

            B----->C----->D---->E
            ^                   |
            |                   V
            W-------->X-------->Y----->Z

            Attaching the path B-->C-->D-->E results in W-->X-->B-->C-->D-->E-->Y-->Z
        """
        branch_node = path.tail
        branch_node_previous = node
        while branch_node.hash not in visited:
            branch_node_previous = branch_node
            branch_node = branch_node.parents[0]

        # make the start of the branch have the parent of the merge
        branch_node_previous.parents[0] = node.parents[0]

        # Removing the main branch parent and replacing it with branch tail
        node.parents[0] = node.parents.pop()

        return Branch(branch_node_previous, node)

    def _inline_branches(self):
        """Inlines the branches by finding each merge commit, tracing the path
        back to where it checks out from main, and stitching the branch.
        After stitching it goes back to start of the branch and finds the next
        merge commit, therefore any branching off the branch is also inlined
        """
        visited = set()
        current_node = self._main_branch.head
        while current_node is not None:
            visited.add(current_node.hash)
            if len(current_node.parents) != 2:
                # we only want the merge commits
                current_node = self.get_successor(current_node)
                continue

            if current_node.parents[1].hash in visited:
                path = Branch(current_node.parents[1], current_node.parents[1])
            else:
                path = self._trace_path_back_to_main(current_node.parents[1])

            stitched_branch = self._stitch_path(current_node, path, visited)
            visited.update(stitched_branch.commits)

            # go back to the start of the branch
            current_node = stitched_branch.head

    def __iter__(self) -> Iterator[list[FileChanges]]:
        """Converts the branches into rows of FileChanges"""
        rows: list[list[FileChanges]] = []
        current_node: Optional[CommitNode] = self._main_branch.head
        while current_node is not None:
            rows.append(current_node.changes)
            current_node = self.get_successor(current_node)
        return iter(rows)
