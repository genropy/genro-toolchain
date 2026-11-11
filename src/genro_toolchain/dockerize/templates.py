"""Files written into the Docker build context.

The gunicorn and supervisord templates match ``gnr app dockerize``, so images
behave the same at runtime."""

from __future__ import annotations

GUNICORN_TEMPLATE = """
import multiprocessing

def get_cpu_limit():
    # cgroup v2
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            quota, period = f.read().strip().split()
            if quota != "max":
                return max(1, int(int(quota) / int(period)))
    except FileNotFoundError:
        pass

    # cgroup v1 fallback
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as q:
            quota = int(q.read())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as p:
            period = int(p.read())
        if quota > 0:
            return max(1, int(quota / period))
    except FileNotFoundError:
        pass

    # fallback (not in k8s or no limits)
    return multiprocessing.cpu_count() or 1

bind = '0.0.0.0:8888'
pidfile = '/home/genro/gunicorn_{instance_name}.pid'
daemon = False
workers = get_cpu_limit()
threads = 8
loglevel = 'error'
chdir = '{instance_folder}'
reload = False
capture_output = True
max_requests = 600
max_requests_jitter = 50
timeout = 1800
graceful_timeout = 600
"""

SUPERVISORD_TEMPLATE = """
[supervisord]
nodaemon = true

[program:dbsetup]
priority=1
autorestart=unexpected
startsecs = 0
exitcodes = 0
command=gnr db migrate -u {instance_name}
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0


[program:httpserver]
priority=50
command=gnr web serveprod {instance_name} -c /home/genro/gunicorn.py
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:gnrasync]
priority=999
command=gnr app async -p 9999 {instance_name}
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:gnrtaskscheduler]
priority=999
autorestart=false
command=gnr web taskscheduler {instance_name}
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:gnrtaskworker]
priority=999
command=gnr web taskworker {instance_name}
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
"""


def gunicorn_conf(instance_name: str, instance_folder: str) -> str:
    return GUNICORN_TEMPLATE.format(instance_name=instance_name, instance_folder=instance_folder)


def supervisord_conf(instance_name: str) -> str:
    return SUPERVISORD_TEMPLATE.format(instance_name=instance_name)


def label_instruction(labels: dict[str, str]) -> str:
    """A single LABEL instruction, one ``key="value"`` per continuation line."""

    def quote(text: str) -> str:
        return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'

    return "LABEL " + " \\\n\t ".join(f"{quote(k)}={quote(v)}" for k, v in labels.items())
