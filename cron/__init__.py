"""Cron job scheduling system for Hermes Agent.

This module provides scheduled task execution, allowing the agent to:
- Run automated tasks on schedules (cron expressions, intervals, one-shot)
- Self-schedule reminders and follow-up tasks
- Execute tasks in isolated sessions (no prior context)

Cron jobs are executed automatically by the gateway daemon:
    hermes gateway install    # Install as a user service
    sudo hermes gateway install --system  # Linux servers: boot-time system service
    hermes gateway            # Or run in foreground

The gateway ticks the scheduler every 60 seconds. A file lock prevents
duplicate execution if multiple processes overlap.
"""

from cron.jobs import (
    JOBS_FILE,
    create_job,
    get_job,
    list_jobs,
    pause_job,
    remove_job,
    resume_job,
    trigger_job,
    update_job,
)
from cron.scheduler import tick

__all__ = [
    "JOBS_FILE",
    "create_job",
    "get_job",
    "list_jobs",
    "pause_job",
    "remove_job",
    "resume_job",
    "tick",
    "trigger_job",
    "update_job",
]
