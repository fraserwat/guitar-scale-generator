from django.db import models


class AttemptLog(models.Model):
    """One logged attempt at a practice round."""

    form_id = models.CharField(max_length=64)  # fingering form config id
    scale = models.CharField(max_length=64)
    key = models.CharField(max_length=3)
    direction = models.CharField(max_length=16)
    correct = models.BooleanField()
    is_retry = models.BooleanField(default=False)  # re-ask of a round just missed
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        mark = "correct" if self.correct else "incorrect"
        return f"{self.key} {self.scale} {self.direction} — {mark}"
