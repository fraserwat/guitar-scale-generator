# guitar-scale-generator
Wanting a more efficient way of keeping up with scales, not forgetting them, but also not spending too much time on them. Also a proof of concept for Claude Fable 5.

## TODOs

- [ ] Validate with Major Scale forms.
- [x] Put secret key in .env (setup: `cp .env.example .env`, then generate a key with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` and paste it into `DJANGO_SECRET_KEY`; `DJANGO_DEBUG` and `DJANGO_ALLOWED_HOSTS` are also read from `.env`).
- [ ] Push to production.
- [ ] Separate correct & incorrect in results (incorrect first).
- [ ] Confirm & update scale configs.
- [ ] Real TAB rendering.
- [ ] Flat/sharp spelling.
- [ ] Reconcile with fraserwatt.dev website theme.
- [ ] Select scale types from practice menu.
- [ ] Repeat in Queue+3 if incorrect.
- [ ] 7-string scale forms.
- [ ] Users/auth.
- [ ] Spaced repetition algorithm.
- [ ] Config hot-reload.
