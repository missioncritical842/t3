from nautobot.apps.jobs import Job, register_jobs


class MinimalTest(Job):
    """Minimal diagnostic job -- no external imports."""

    class Meta:
        name = "Minimal Test"
        description = "No-op diagnostic job to test Git repo job registration."
        commit_default = False
        has_sensitive_variables = False

    def run(self, **kwargs):
        self.logger.info("MinimalTest: job loaded and running OK")
        return "OK"


register_jobs(MinimalTest)
