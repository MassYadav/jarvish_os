from __future__ import annotations

from pathlib import Path
import os
import subprocess


class ProcessServiceError(RuntimeError):
    """Raised when an application cannot be launched safely."""


class ProcessService:
    def launch(
        self,
        *,
        application: str,
        args: list[str] | None = None,
        working_directory: str | None = None,
    ) -> dict[str, int | str | list[str] | None]:
        command = self._build_command(application=application, args=args or [])
        cwd = self._resolve_working_directory(working_directory)

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            raise ProcessServiceError(f"Unable to launch application: {exc}") from exc

        return {
            "pid": process.pid,
            "application": application,
            "args": args or [],
            "working_directory": cwd,
        }

    def _build_command(self, *, application: str, args: list[str]) -> list[str]:
        normalized_application = application.strip().strip('"').strip("'")
        if not normalized_application:
            raise ProcessServiceError("Application cannot be empty")

        safe_args = []
        for arg in args:
            if "\x00" in arg:
                raise ProcessServiceError("Process argument contains a null byte")
            safe_args.append(arg)

        return [normalized_application, *safe_args]

    def _resolve_working_directory(self, working_directory: str | None) -> str | None:
        if working_directory is None:
            return None

        resolved = Path(working_directory).expanduser().resolve()
        if not resolved.exists():
            raise ProcessServiceError(f"Working directory does not exist: {resolved}")
        if not resolved.is_dir():
            raise ProcessServiceError(f"Working directory is not a directory: {resolved}")

        return os.fspath(resolved)


process_service = ProcessService()
