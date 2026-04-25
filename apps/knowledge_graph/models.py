from django.db import models


class GraphSnapshot(models.Model):
    data = models.JSONField()
    generated_at = models.DateTimeField(auto_now=True)
    git_head = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = 'Graph Snapshot'

    def __str__(self):
        return f"GraphSnapshot @ {self.generated_at} ({self.git_head[:7] if self.git_head else 'no-git'})"
