/* ScaleRunner — game logic (vanilla JS, no build step). */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var CSRF_TOKEN = document.body.dataset.csrfToken;

  // ---- Elements -----------------------------------------------------------
  var appTitleEl = document.querySelector(".app-title");
  var startScreen = document.getElementById("start-screen");
  var exerciseScreen = document.getElementById("exercise-screen");
  var resultsScreen = document.getElementById("results-screen");
  var startBtn = document.getElementById("start-btn");
  var exerciseChecks = Array.prototype.slice.call(
    document.querySelectorAll(".exercise-checkbox"));
  var exerciseHintEl = document.getElementById("exercise-hint");
  var startWrapEl = document.getElementById("start-wrap");
  var timerEl = document.getElementById("timer");
  var roundKeyEl = document.getElementById("round-key");
  var roundScaleEl = document.getElementById("round-scale");
  var roundDirectionEl = document.getElementById("round-direction");
  var roundLabelEl = document.getElementById("round-label");
  var neckSvg = document.getElementById("neck");
  var tabSvg = document.getElementById("tab");
  var hintEl = document.getElementById("hint");
  var correctBtn = document.getElementById("correct-btn");
  var incorrectBtn = document.getElementById("incorrect-btn");
  var resultsSummaryEl = document.getElementById("results-summary");
  var resultsScoreEl = document.getElementById("results-score");
  var resultsPctEl = document.getElementById("results-pct");
  var resultsBarFillEl = document.getElementById("results-bar-fill");
  var resultsEmptyEl = document.getElementById("results-empty");
  var resultsGroupCorrectEl = document.getElementById("results-group-correct");
  var resultsGroupIncorrectEl = document.getElementById("results-group-incorrect");
  var resultsCountCorrectEl = document.getElementById("results-count-correct");
  var resultsCountIncorrectEl = document.getElementById("results-count-incorrect");
  var resultsListCorrectEl = document.getElementById("results-list-correct");
  var resultsListIncorrectEl = document.getElementById("results-list-incorrect");
  var againBtn = document.getElementById("again-btn");

  // Server-rendered hint markup (index.html), restored at each new round.
  var HINT_DEFAULT = hintEl.innerHTML;

  // ---- State --------------------------------------------------------------
  var phase = "idle"; // idle | loading | play | reveal | results
  var timeLeft = 0;
  var timerId = null;
  var currentRound = null;
  var rounds = [];
  var retryQueue = []; // [{round, delay}] — failed rounds due again in `delay` turns
  var isRetry = false; // is currentRound a re-ask of a missed round?
  var overtime = false; // timer expired, draining retryQueue before results
  var roundQuery = ""; // "?scales=..." for this session; "" = all exercises

  // ---- Neck SVG geometry ----------------------------------------------------
  // viewBox 560x240. Low E (string 6) at the BOTTOM, per fretboard-diagram
  // convention. 6 fret spaces; a note "at fret N" sits in the space whose
  // right-hand line is fret wire N.
  var NECK = {
    left: 40, top: 25,
    fretW: 80, stringGap: 30,
    nFrets: 6, nStrings: 6
  };
  NECK.right = NECK.left + NECK.nFrets * NECK.fretW;
  NECK.bottom = NECK.top + (NECK.nStrings - 1) * NECK.stringGap;

  function el(name, attrs, text) {
    var node = document.createElementNS(SVG_NS, name);
    Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // y coordinate for a string number (1 = high e at top ... 6 = low E at bottom)
  function stringY(stringNum) {
    return NECK.top + (stringNum - 1) * NECK.stringGap;
  }

  /** First fret shown on the neck. The window is 6 frets wide; a 4-fret
   *  shape sits centred in it (one empty fret each side) instead of
   *  hugging the left edge. Wider shapes anchor on their lowest fret as
   *  served. (A shape at fret 1 can't shift down — there's no fret 0.) */
  function viewStart(round) {
    var top = Math.max.apply(null, round.notes.map(function (n) {
      return n.fret;
    }));
    var span = top - round.window_start + 1;
    return (span === 4 && round.window_start > 1)
      ? round.window_start - 1
      : round.window_start;
  }

  /** The wordmark's glossy shine-line fill at dot scale: lighter upper
   *  half with a hard drop at the middle. */
  function glossGradient(id, tones) {
    var grad = el("linearGradient", { id: id, x1: 0, y1: 0, x2: 0, y2: 1 });
    [[0, tones[0]], [0.5, tones[1]], [0.5, tones[2]], [1, tones[3]]]
      .forEach(function (stop) {
        grad.appendChild(el("stop", {
          offset: stop[0], "stop-color": stop[1]
        }));
      });
    return grad;
  }

  /** Draw the empty neck: strings, fret lines, and HIDDEN fret-number
   *  labels. The labels would give the position away, so they stay hidden
   *  until the answer phase (revealed together with the note dots). */
  function drawNeck(windowStart) {
    neckSvg.textContent = "";

    // Dot fills (CSS references these by id); redrawn with the neck.
    var defs = el("defs", {});
    defs.appendChild(glossGradient("dot-orange",
      ["#ffc98a", "#ffb964", "#f9993a", "#ffab4a"]));
    defs.appendChild(glossGradient("dot-dark",
      ["#39424f", "#232b36", "#0c0f14", "#10141b"]));
    neckSvg.appendChild(defs);

    // Fret lines (vertical). Leftmost line is fret wire windowStart - 1.
    for (var i = 0; i <= NECK.nFrets; i++) {
      var x = NECK.left + i * NECK.fretW;
      neckSvg.appendChild(el("line", {
        x1: x, y1: NECK.top, x2: x, y2: NECK.bottom,
        "class": "fret-line", "stroke-width": i === 0 ? 4 : 2
      }));
    }

    // Strings (horizontal), thicker towards low E.
    for (var s = 1; s <= NECK.nStrings; s++) {
      neckSvg.appendChild(el("line", {
        x1: NECK.left, y1: stringY(s), x2: NECK.right, y2: stringY(s),
        "class": "string-line", "stroke-width": 1 + (s - 1) * 0.4
      }));
    }

    // Fret-number labels under each fret space, hidden during the question
    // phase. reveal() unhides the group; each new round redraws the neck so
    // they start hidden again.
    var labels = el("g", { id: "fret-labels", display: "none" });
    for (var f = 0; f < NECK.nFrets; f++) {
      labels.appendChild(el("text", {
        x: NECK.left + (f + 0.5) * NECK.fretW,
        y: NECK.bottom + 35,
        "text-anchor": "middle",
        "class": "fret-label"
      }, String(windowStart + f)));
    }
    neckSvg.appendChild(labels);
  }

  /** Unhide the fret-number labels (answer phase only). */
  function revealFretLabels() {
    var labels = neckSvg.querySelector("#fret-labels");
    if (labels) labels.removeAttribute("display");
  }

  /** Fill the neck with the round's note dots (roots highlighted). */
  function drawNotes(round) {
    var start = viewStart(round);
    var dots = el("g", { id: "note-dots" });
    round.notes.forEach(function (note) {
      var cx = NECK.left + (note.fret - start + 0.5) * NECK.fretW;
      var cy = stringY(note.string);
      var dot = note.is_root
        ? el("circle", { cx: cx, cy: cy, r: 10, "class": "root" })
        : el("circle", { cx: cx, cy: cy, r: 9, "class": "note-dot" });
      dot.appendChild(el("title", {}, note.note_name));
      dots.appendChild(dot);
    });
    neckSvg.appendChild(dots);
  }

  // ---- TAB ------------------------------------------------------------------
  // Six-line staff redrawn per round; the run's numbers are laid out into a
  // HIDDEN group (like the neck's fret labels) and revealed with the answer.
  var TAB = { left: 32, right: 545, top: 20, lineGap: 18 };

  // y coordinate for a string number on the TAB staff (1 = high e at top).
  function tabY(stringNum) {
    return TAB.top + (stringNum - 1) * TAB.lineGap;
  }

  /** Draw the TAB staff; with a round, also lay out the run's numbers.
   *  The API's notes arrive in ascending play order (low string first, then
   *  fret), so Ascending renders as-is left to right from the low root and
   *  Descending is the same run reversed, starting on the top note. */
  function drawTab(round) {
    tabSvg.textContent = "";
    var labels = ["e", "B", "G", "D", "A", "E"];
    for (var i = 0; i < 6; i++) {
      var y = TAB.top + i * TAB.lineGap;
      tabSvg.appendChild(el("text", {
        x: 18, y: y + 5, "text-anchor": "middle", "class": "tab-label"
      }, labels[i]));
      tabSvg.appendChild(el("line", {
        x1: TAB.left, y1: y, x2: TAB.right, y2: y, "class": "tab-line"
      }));
    }
    if (!round) return; // start screen: staff only, no run yet

    var seq = round.notes.slice();
    if (round.direction === "Descending") seq.reverse();

    var numbers = el("g", { id: "tab-numbers", display: "none" });
    var colW = (TAB.right - TAB.left - 10) / seq.length;
    seq.forEach(function (note, idx) {
      var cx = TAB.left + 10 + (idx + 0.5) * colW;
      var cy = tabY(note.string);
      // Mask the staff line behind the number (conventional TAB look).
      numbers.appendChild(el("rect", {
        x: cx - 8, y: cy - 7, width: 16, height: 14, "class": "tab-mask"
      }));
      var num = el("text", {
        x: cx, y: cy + 5, "text-anchor": "middle", "class": "tab-num"
      }, String(note.fret));
      if (note.is_root) num.setAttribute("class", "tab-num root");
      num.appendChild(el("title", {}, note.note_name));
      numbers.appendChild(num);
    });
    tabSvg.appendChild(numbers);
  }

  /** Unhide the TAB numbers (answer phase only). */
  function revealTabNumbers() {
    var numbers = tabSvg.querySelector("#tab-numbers");
    if (numbers) numbers.removeAttribute("display");
  }

  // ---- Screens & timer ------------------------------------------------------
  function showScreen(screen) {
    [startScreen, exerciseScreen, resultsScreen].forEach(function (s) {
      s.classList.toggle("hidden", s !== screen);
    });
  }

  function formatTime(seconds) {
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + ":" + String(s).padStart(2, "0");
  }

  function tick() {
    timeLeft -= 1;
    timerEl.textContent = formatTime(Math.max(timeLeft, 0));
    timerEl.classList.toggle("timer-low", timeLeft <= 30);
    if (timeLeft > 0) return;
    clearInterval(timerId);
    timerId = null;
    if (retryQueue.length === 0) { endGame(); return; }
    overtime = true; // finish the in-flight round, then drain the queue
  }

  // ---- Exercise picker ------------------------------------------------------
  function checkedScaleIds() {
    return exerciseChecks
      .filter(function (c) { return c.checked; })
      .map(function (c) { return c.value; });
  }

  /** All boxes checked -> "" (cleanest URL and keeps the default no-param
   *  server path exercised); otherwise the ?scales= filter. Ids are
   *  server-rendered config slugs, so no URL-encoding is needed. */
  function buildScalesQuery() {
    var ids = checkedScaleIds();
    if (ids.length === exerciseChecks.length) return "";
    return "?scales=" + ids.join(",");
  }

  /** Empty selection: Start disabled + hint shown. */
  function updateStartState() {
    var any = checkedScaleIds().length > 0;
    startBtn.disabled = !any;
    exerciseHintEl.classList.toggle("hidden", any);
  }

  // ---- Game flow ------------------------------------------------------------
  function startGame() {
    // Computed once per session; every fresh-round fetch reuses it. Retry
    // rounds replay stored round objects and never fetch, so a queued miss
    // stays owed regardless of the filter — that's deliberate.
    roundQuery = buildScalesQuery();
    rounds = [];
    retryQueue = [];
    isRetry = false;
    overtime = false;
    timeLeft = parseInt(document.querySelector(
      'input[name="timer-length"]:checked').value, 10) * 60;
    timerEl.textContent = formatTime(timeLeft);
    timerEl.classList.remove("timer-low");
    showScreen(exerciseScreen);
    drawTab(null);
    timerId = setInterval(tick, 1000);
    nextRound();
  }

  /** Pop the retry round due this turn, if any. Each nextRound() call is
   *  one turn, so every queued entry counts down by 1 and the first entry
   *  that reaches 0 (oldest first) is served. In overtime the delays are
   *  moot — the queue just drains FIFO, back-to-back, with no fresh rounds
   *  interleaved (the 2-turn gap is deliberately not preserved there:
   *  overtime exists only to give pending retries their second chance). */
  function takeDueRetry() {
    if (retryQueue.length === 0) return null;
    if (overtime) return retryQueue.shift();
    retryQueue.forEach(function (e) { e.delay -= 1; });
    for (var i = 0; i < retryQueue.length; i++) {
      if (retryQueue[i].delay <= 0) return retryQueue.splice(i, 1)[0];
    }
    return null;
  }

  function nextRound() {
    if (overtime && retryQueue.length === 0) { endGame(); return; }
    phase = "loading";
    currentRound = null;
    isRetry = false;
    correctBtn.disabled = true;
    incorrectBtn.disabled = true;
    hintEl.innerHTML = HINT_DEFAULT;

    var due = takeDueRetry();
    if (due) {
      // Re-asks render from the stored round object — no fetch, and no
      // visual distinction from a fresh round.
      isRetry = true;
      presentRound(due.round);
    } else {
      fetchFreshRound();
    }
  }

  function presentRound(round) {
    currentRound = round;
    // Header reads e.g. "C Major Pentatonic — E Shape · Descending" or
    // "A Natural Minor Scale — 2nd Finger Form · Ascending";
    // display_label carries the category-appropriate language.
    roundKeyEl.textContent = round.key;
    roundScaleEl.textContent = round.scale;
    roundLabelEl.textContent = round.display_label;
    roundDirectionEl.textContent = round.direction;
    drawNeck(viewStart(round)); // UNFILLED (and unlabelled) until spacebar
    drawTab(round); // staff visible, numbers hidden until spacebar
    phase = "play";
  }

  function fetchFreshRound() {
    fetch("/api/round/" + roundQuery)
      .then(function (resp) {
        if (!resp.ok) throw new Error("round fetch failed: " + resp.status);
        return resp.json();
      })
      .then(function (round) {
        if (phase !== "loading") return; // game may have ended meanwhile
        presentRound(round);
      })
      .catch(function (err) {
        hintEl.textContent = "Could not load a round (" + err.message + "). Retrying…";
        // Retry the FETCH only — going back through nextRound() would
        // decrement retryQueue delays again for the same turn.
        setTimeout(function () { if (phase === "loading") fetchFreshRound(); }, 1500);
      });
  }

  function reveal() {
    if (phase !== "play" || !currentRound) return;
    drawNotes(currentRound);
    revealFretLabels();
    revealTabNumbers();
    correctBtn.disabled = false;
    incorrectBtn.disabled = false;
    phase = "reveal";
  }

  function judge(correct) {
    if (phase !== "reveal" || !currentRound) return;
    var round = currentRound;
    var wasRetry = isRetry; // nextRound() resets the flag before the POST fires
    rounds.push({
      form_id: round.form_id,
      form_name: round.form_name,
      display_label: round.display_label,
      scale: round.scale,
      key: round.key,
      direction: round.direction,
      correct: correct
    });

    // A miss goes back in the queue and is re-asked two turns from now
    // (and again after that if the retry also misses). The FULL round
    // object is stored so the re-ask renders without a fetch.
    if (!correct) retryQueue.push({ round: round, delay: 2 });

    // Best-effort attempt log — a failed POST never blocks the game.
    fetch("/api/log/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": CSRF_TOKEN
      },
      body: JSON.stringify({
        form_id: round.form_id,
        scale: round.scale,
        key: round.key,
        direction: round.direction,
        correct: correct,
        is_retry: wasRetry
      })
    }).catch(function () { /* see comment above */ });

    nextRound();
  }

  /** One results row. Same language as the round header, e.g.
   *  "F# Dominant 7 Arpeggio — A Shape · Ascending"; the key + scale get
   *  the visual emphasis, the form stays muted and the direction pops
   *  in accent orange (matching the round header). */
  function resultRow(r) {
    var li = document.createElement("li");
    var name = document.createElement("span");
    name.className = "result-name";
    name.textContent = r.key + " " + r.scale;
    var meta = document.createElement("span");
    meta.className = "result-meta";
    meta.textContent = r.display_label + " · ";
    var dir = document.createElement("span");
    dir.className = "result-direction";
    dir.textContent = r.direction;
    meta.appendChild(dir);
    li.appendChild(name);
    li.appendChild(meta);
    return li;
  }

  /** Fill one outcome group (heading count + list); empty groups hide
   *  entirely so an all-correct (or all-wrong) session stays tidy. */
  function renderGroup(groupEl, countEl, listEl, items) {
    countEl.textContent = String(items.length);
    listEl.textContent = "";
    items.forEach(function (r) { listEl.appendChild(resultRow(r)); });
    groupEl.classList.toggle("hidden", items.length === 0);
  }

  function endGame() {
    clearInterval(timerId);
    timerId = null;
    phase = "results";

    var correct = rounds.filter(function (r) { return r.correct; });
    var incorrect = rounds.filter(function (r) { return !r.correct; });
    var total = rounds.length;
    var pct = total === 0 ? 0 : Math.round((correct.length / total) * 100);

    // Summary card (hidden in favour of the empty-state note when no
    // rounds were completed).
    resultsSummaryEl.classList.toggle("hidden", total === 0);
    resultsEmptyEl.classList.toggle("hidden", total !== 0);
    resultsScoreEl.textContent = correct.length + " / " + total;
    resultsPctEl.textContent = pct + "%";
    resultsBarFillEl.style.width = pct + "%";

    // Outcome groups: correct first, then the ones to revisit.
    renderGroup(resultsGroupCorrectEl, resultsCountCorrectEl,
                resultsListCorrectEl, correct);
    renderGroup(resultsGroupIncorrectEl, resultsCountIncorrectEl,
                resultsListIncorrectEl, incorrect);

    showScreen(resultsScreen);
  }

  // ---- Events ---------------------------------------------------------------
  startBtn.addEventListener("click", startGame);
  exerciseChecks.forEach(function (c) {
    c.addEventListener("change", updateStartState);
  });
  updateStartState(); // belt-and-braces vs. browser form-state restoration
  // Poking the locked Start (clicks pass through it via CSS
  // pointer-events) wiggles the dialog bubble for emphasis.
  startWrapEl.addEventListener("click", function () {
    if (!startBtn.disabled) return;
    exerciseHintEl.classList.remove("bubble-shake");
    void exerciseHintEl.offsetWidth; // restart the animation
    exerciseHintEl.classList.add("bubble-shake");
  });
  // The title is a home link: from any screen it abandons the session
  // (timer stopped, rounds discarded — no results) and shows the menu.
  appTitleEl.addEventListener("click", function () {
    clearInterval(timerId);
    timerId = null;
    phase = "idle";
    showScreen(startScreen);
  });
  againBtn.addEventListener("click", function () {
    phase = "idle";
    showScreen(startScreen);
  });
  correctBtn.addEventListener("click", function (e) {
    e.currentTarget.blur();
    judge(true);
  });
  incorrectBtn.addEventListener("click", function (e) {
    e.currentTarget.blur();
    judge(false);
  });

  // Spacebar: reveal notes. preventDefault on both keydown and keyup so it
  // never scrolls the page or "clicks" a focused button mid-game.
  document.addEventListener("keydown", function (e) {
    if (e.code !== "Space") return;
    if (!exerciseScreen.classList.contains("hidden")) {
      e.preventDefault();
      reveal();
    }
  });

  // Keyboard shorthand: "," = correct, "." = incorrect. Active ONLY in the
  // answer phase (after spacebar, before advancing) — judge() ignores any
  // other phase, and e.repeat guards a held key from double-advancing
  // (judge() itself also flips the phase, so a second press is a no-op).
  document.addEventListener("keydown", function (e) {
    if (e.key !== "," && e.key !== ".") return;
    if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
    if (exerciseScreen.classList.contains("hidden")) return;
    if (phase !== "reveal") return;
    e.preventDefault();
    judge(e.key === ",");
  });
  document.addEventListener("keyup", function (e) {
    if (e.code === "Space" && !exerciseScreen.classList.contains("hidden")) {
      e.preventDefault();
    }
  });
})();
