/* Guitar Scale Practice — game logic (vanilla JS, no build step). */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var CSRF_TOKEN = document.body.dataset.csrfToken;

  // ---- Elements -----------------------------------------------------------
  var startScreen = document.getElementById("start-screen");
  var exerciseScreen = document.getElementById("exercise-screen");
  var resultsScreen = document.getElementById("results-screen");
  var timerLengthEl = document.getElementById("timer-length");
  var startBtn = document.getElementById("start-btn");
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
  var resultsTotalsEl = document.getElementById("results-totals");
  var resultsListEl = document.getElementById("results-list");
  var againBtn = document.getElementById("again-btn");

  // ---- State --------------------------------------------------------------
  var phase = "idle"; // idle | loading | play | reveal | results
  var timeLeft = 0;
  var timerId = null;
  var currentRound = null;
  var rounds = [];

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

  /** Draw the empty neck: strings, fret lines, and HIDDEN fret-number
   *  labels. The labels would give the position away, so they stay hidden
   *  until the answer phase (revealed together with the note dots). */
  function drawNeck(windowStart) {
    neckSvg.textContent = "";

    // Fret lines (vertical). Leftmost line is fret wire windowStart - 1.
    for (var i = 0; i <= NECK.nFrets; i++) {
      var x = NECK.left + i * NECK.fretW;
      neckSvg.appendChild(el("line", {
        x1: x, y1: NECK.top, x2: x, y2: NECK.bottom,
        stroke: "#4b5568", "stroke-width": i === 0 ? 4 : 2
      }));
    }

    // Strings (horizontal), thicker towards low E.
    for (var s = 1; s <= NECK.nStrings; s++) {
      neckSvg.appendChild(el("line", {
        x1: NECK.left, y1: stringY(s), x2: NECK.right, y2: stringY(s),
        stroke: "#b8c2d2", "stroke-width": 1 + (s - 1) * 0.4
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
        fill: "#c5cfde",
        "font-size": 16
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
    var dots = el("g", { id: "note-dots" });
    round.notes.forEach(function (note) {
      var cx = NECK.left + (note.fret - round.window_start + 0.5) * NECK.fretW;
      var cy = stringY(note.string);
      var dot = note.is_root
        ? el("circle", { cx: cx, cy: cy, r: 10, fill: "#f59f3d" })
        : el("circle", {
            cx: cx, cy: cy, r: 9,
            fill: "#0c0f14", stroke: "#eef2f8", "stroke-width": 2.5
          });
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
        x: 18, y: y + 5, "text-anchor": "middle",
        fill: "#aab5c5", "font-size": 13, "font-family": "monospace"
      }, labels[i]));
      tabSvg.appendChild(el("line", {
        x1: TAB.left, y1: y, x2: TAB.right, y2: y,
        stroke: "#4b5568", "stroke-width": 1
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
        x: cx - 8, y: cy - 7, width: 16, height: 14, fill: "#0c0f14"
      }));
      var num = el("text", {
        x: cx, y: cy + 5, "text-anchor": "middle",
        fill: note.is_root ? "#f59f3d" : "#eef2f8",
        "font-size": 13, "font-family": "monospace",
        "font-weight": note.is_root ? "bold" : "normal"
      }, String(note.fret));
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
    if (timeLeft <= 0) endGame();
  }

  // ---- Game flow ------------------------------------------------------------
  function startGame() {
    rounds = [];
    timeLeft = parseInt(timerLengthEl.value, 10) * 60;
    timerEl.textContent = formatTime(timeLeft);
    showScreen(exerciseScreen);
    drawTab(null);
    timerId = setInterval(tick, 1000);
    nextRound();
  }

  function nextRound() {
    phase = "loading";
    currentRound = null;
    correctBtn.disabled = true;
    incorrectBtn.disabled = true;
    hintEl.innerHTML =
      "Play the scale, then press <kbd>SPACE</kbd> to reveal the notes.";

    fetch("/api/round/")
      .then(function (resp) {
        if (!resp.ok) throw new Error("round fetch failed: " + resp.status);
        return resp.json();
      })
      .then(function (round) {
        if (phase !== "loading") return; // game may have ended meanwhile
        currentRound = round;
        // Header reads e.g. "C Major Pentatonic — E Shape · Descending" or
        // "A Natural Minor Scale — 2nd Finger Form · Ascending";
        // display_label carries the category-appropriate language.
        roundKeyEl.textContent = round.key;
        roundScaleEl.textContent = round.scale;
        roundLabelEl.textContent = round.display_label;
        roundDirectionEl.textContent = round.direction;
        drawNeck(round.window_start); // UNFILLED (and unlabelled) until spacebar
        drawTab(round); // staff visible, numbers hidden until spacebar
        phase = "play";
      })
      .catch(function (err) {
        hintEl.textContent = "Could not load a round (" + err.message + "). Retrying…";
        setTimeout(function () { if (phase === "loading") nextRound(); }, 1500);
      });
  }

  function reveal() {
    if (phase !== "play" || !currentRound) return;
    drawNotes(currentRound);
    revealFretLabels();
    revealTabNumbers();
    correctBtn.disabled = false;
    incorrectBtn.disabled = false;
    hintEl.textContent = "Did you play it right?";
    phase = "reveal";
  }

  function judge(correct) {
    if (phase !== "reveal" || !currentRound) return;
    var round = currentRound;
    rounds.push({
      form_id: round.form_id,
      form_name: round.form_name,
      display_label: round.display_label,
      scale: round.scale,
      key: round.key,
      direction: round.direction,
      correct: correct
    });

    // Logging stub endpoint. TODO(spaced repetition): this data will drive
    // round selection weighting server-side later.
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
        correct: correct
      })
    }).catch(function () { /* logging is best-effort in v1 */ });

    nextRound();
  }

  function endGame() {
    clearInterval(timerId);
    timerId = null;
    phase = "results";

    var total = rounds.length;
    var nCorrect = rounds.filter(function (r) { return r.correct; }).length;
    resultsTotalsEl.textContent = total === 0
      ? "No rounds completed."
      : nCorrect + " / " + total + " correct";

    resultsListEl.textContent = "";
    rounds.forEach(function (r) {
      var li = document.createElement("li");
      li.className = r.correct ? "result-correct" : "result-incorrect";
      var desc = document.createElement("span");
      // Same language as the round header, e.g.
      // "F# Dominant 7 Arpeggio — A Shape · Ascending".
      desc.textContent =
        r.key + " " + r.scale + " — " + r.display_label + " · " + r.direction;
      var mark = document.createElement("span");
      mark.className = r.correct ? "result-mark-correct" : "result-mark-incorrect";
      mark.textContent = r.correct ? "✓ correct" : "✗ incorrect";
      li.appendChild(desc);
      li.appendChild(mark);
      resultsListEl.appendChild(li);
    });

    showScreen(resultsScreen);
  }

  // ---- Events ---------------------------------------------------------------
  startBtn.addEventListener("click", startGame);
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
