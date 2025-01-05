from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Iterator, Optional, Self

from src.discriminators.types import FileChanges


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
        commits = set()
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
        self._predecessor: dict[str, Optional[CommitNode]] = dict()
        self._main_branch = self._make_main_branch(self._changes)
        self._inline_branches()

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

        for commit_hash, commit in commits:
            changes: list[FileChanges] = list(commit)
            parents = (
                [nodes[parent] for parent in changes[0]["parents"].split("|")]
                if changes[0]["parents"]
                else []
            )
            nodes[commit_hash] = CommitNode(
                hash=commit_hash, changes=changes, parents=parents
            )

            self._predecessor[commit_hash] = parents[0] if parents else None

        assert (
            nodes[commits[0][0]].parents == []
        ), "The first commit should have no parents"
        assert (
            commits[-1][0] not in self._predecessor.values()
        ), "The last commit should have no children"

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
        """Stitches the branch into the node given


        Example:

            B----->C----->D---->E
            ^                   |
            |                   V
            W-------->X-------->Y----->Z

            Attaching the path B-->C-->D-->E results in


            W-->X-->B-->C-->D-->E-->Y-->Z
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

        self._predecessor[node.hash] = path.tail
        self._predecessor[branch_node_previous.hash] = node.parents[0]

        return Branch(node, path.tail)

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
                current_node = self._predecessor[current_node.hash]
                continue

            print(f"Merging branch with tail {current_node.hash} | {len(visited)}")
            path = self._trace_path_back_to_main(current_node.parents[1])

            stitched_branch = self._stitch_path(current_node, path, visited)
            visited.update(stitched_branch.commits)

            # go back to the start of the branch
            current_node = stitched_branch.head

    def __iter__(self) -> Iterator[list[FileChanges]]:
        """Converts the branches into rows of FileChanges"""
        rows: list[list[FileChanges]] = []
        current_node: Optional[CommitNode] = self._main_branch.tail
        while current_node is not None:
            rows.append(current_node.changes)
            current_node = current_node.parents[0] if current_node.parents else None
        return reversed(rows)
