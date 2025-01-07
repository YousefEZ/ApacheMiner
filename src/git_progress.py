from typing import Optional, Self, Union

import git
import rich.progress


class CloneProgress(git.RemoteProgress):
    code_map_name = {
        git.RemoteProgress.BEGIN: "Starting...",
        git.RemoteProgress.END: "Finished",
        git.RemoteProgress.COUNTING: "Counting...",
        git.RemoteProgress.COMPRESSING: "Compressing...",
        git.RemoteProgress.WRITING: "Writing...",
        git.RemoteProgress.RECEIVING: "Receiving...",
        git.RemoteProgress.RESOLVING: "Resolving...",
        git.RemoteProgress.FINDING_SOURCES: "Finding Sources...",
        git.RemoteProgress.CHECKING_OUT: "Checking Out...",
    }

    def __init__(self) -> None:
        super().__init__()
        self.active_task: Optional[rich.progress.TaskID] = None
        self.progressbar = rich.progress.Progress(
            rich.progress.SpinnerColumn(),
            rich.progress.TextColumn("[progress.description]{task.description}"),
            rich.progress.BarColumn(),
            rich.progress.TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "eta",
            rich.progress.TimeRemainingColumn(),
            rich.progress.TextColumn("{task.fields[message]}"),
            console=rich.console.Console(),
            transient=False,
        )

    def __enter__(self) -> Self:
        self.progressbar.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.progressbar.stop()
        if exc_type:
            raise exc_type(exc_value).with_traceback(exc_tb)

    def update(
        self,
        op_code: int,
        cur_count: Union[str, float],
        max_count: Union[str, float, None] = None,
        message: str = "",
    ) -> None:
        # Start on BEGIN flag
        if op_code & self.BEGIN:
            self.curr_op = self.code_map_name.get(
                op_code & self.OP_MASK, "unknown stage..."
            )
            assert not isinstance(max_count, str)
            self.active_task = self.progressbar.add_task(
                description=self.curr_op,
                total=max_count,
                message=message,
            )

        assert self.active_task is not None, "No active task found"
        assert not isinstance(cur_count, str)
        self.progressbar.update(
            task_id=self.active_task,
            completed=cur_count,
            message=message,
        )

        if op_code & self.END:
            self.progressbar.update(
                task_id=self.active_task,
                message=f"[bright_black]{message}",
            )

    def __call__(
        self,
        op_code: int,
        cur_count: Union[str, float],
        max_count: Union[str, float, None] = None,
        message: str = "",
    ) -> None:
        self.update(op_code, cur_count, max_count, message)
