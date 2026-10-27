import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  History,
  Lightbulb,
  LoaderCircle,
  Puzzle,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { AppLayout } from "./AppLayout";
import { PublicLayout } from "./PublicLayout";
import { Board } from "./Board";
import { SquareTrack, sessionStates } from "./SquareTrack";
import { HiddenScore } from "./HiddenScore";
import { playLocally } from "./local-puzzle";
import { describeMove } from "./describe-move";
import { play } from "./sound";
import { ProfilePage } from "./ProfilePage";
import { ChoiceSelect } from "./ChoiceSelect";
import { ApiError, jsonRequest, useApi } from "./api";
import type {
  Activity,
  LearningHome,
  LearningHistory,
  LearningSession,
  LearningSummary,
  Profile,
} from "./types";

const navigation = [
  { id: "home", label: "Sessions", href: "#/home" },
  { id: "history", label: "History", href: "#/history" },
  { id: "profile", label: "Profile", href: "#/profile" },
];
function readRoute() {
  const [path, query = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [mode, id] = path.split("/");
  return {
    mode: ["home", "history", "profile", "session"].includes(mode)
      ? mode
      : "home",
    id,
    page: Math.max(
      1,
      Math.min(1_000_000, Number(new URLSearchParams(query).get("page")) || 1),
    ),
  };
}
function dateLabel(time: number) {
  return new Date(time * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
function SessionRow({ item }: { item: LearningSummary }) {
  return (
    <a href={`#/session/${item.id}`} className="session-row">
      <span className="session-score">
        {item.solved}
        <small>
          {" "}
          / {item.completed ? item.total : item.finished_count} solved
        </small>
      </span>
      <span className="session-row-name">
        <strong>
          {item.total === 10
            ? "Quick"
            : item.total === 20
              ? "Standard"
              : "Extended"}{" "}
          session
        </strong>
        <small>
          {dateLabel(item.started_at)} · {item.total} puzzles
        </small>
      </span>
      {item.outcomes.length ? (
        <SquareTrack
          className="session-row-track"
          states={sessionStates(item, item.finished_count)}
        />
      ) : null}
      <span
        className="session-status"
        data-active={item.completed ? undefined : "true"}
      >
        {item.completed ? "Completed" : "In progress"}
      </span>
      <ChevronRight className="size-4" aria-hidden="true" />
    </a>
  );
}
function OnboardingIntro({
  profile,
  resume,
  busy,
  start,
}: {
  profile: Profile;
  resume: boolean;
  busy: boolean;
  start: (values: Partial<Profile>) => void;
}) {
  const [experience, setExperience] = useState(profile.experience);
  const [research, setResearch] = useState(profile.research_consent);
  const [analytics, setAnalytics] = useState(profile.analytics_consent);
  return (
    <section className="onboarding-intro">
      <div className="onboarding-story">
        <h1 tabIndex={-1}>Let’s find your level.</h1>
        <p className="intro-copy">
          Ten puzzles, one starting point. We’ll adjust the difficulty as you
          go.
        </p>
        <SquareTrack
          className="onboarding-track"
          states={Array.from({ length: 10 }, () => "upcoming")}
        />
      </div>
      <Card className="onboarding-card">
        <CardContent>
          <div className="assessment-facts">
            <span>
              <Puzzle aria-hidden="true" />
              10 puzzles
            </span>
            <span>
              <Lightbulb aria-hidden="true" />
              Without hints
            </span>
            <span>
              <RotateCcw aria-hidden="true" />
              Resume anytime
            </span>
          </div>
          <div className="field-block">
            <Label htmlFor="onboarding-experience">
              How much chess have you played?
            </Label>
            <ChoiceSelect
              id="onboarding-experience"
              value={experience}
              onValueChange={(value) =>
                setExperience(value as Profile["experience"])
              }
              options={[
                { value: "unspecified", label: "Prefer not to say" },
                { value: "new", label: "I’m new to chess" },
                { value: "casual", label: "I play casually" },
                { value: "club", label: "I play at club level" },
                { value: "advanced", label: "I’m an experienced player" },
              ]}
            />
          </div>
          <div className="consent-section">
            <div className="consent-title">
              <ShieldCheck aria-hidden="true" />
              <h2>Research participation</h2>
              <span className="consent-optional">Optional</span>
            </div>
            <p>
              Your account saves puzzles, moves, hints and results. Research
              participation also lets us analyze those records, confidence and
              session feedback under a participant code.
            </p>
            <div className="check-row">
              <Checkbox
                id="onboarding-research"
                checked={research}
                onCheckedChange={(checked) => setResearch(checked === true)}
              />
              <Label htmlFor="onboarding-research">
                Use my puzzle records for research.
              </Label>
            </div>
            <div className="check-row">
              <Checkbox
                id="onboarding-analytics"
                checked={analytics}
                onCheckedChange={(checked) => setAnalytics(checked === true)}
              />
              <Label htmlFor="onboarding-analytics">
                Include board selections and focus changes.
              </Label>
            </div>
            <p className="consent-note">
              You can change consent, export records or delete your profile at
              any time.
            </p>
          </div>
          <Button
            size="lg"
            className="w-full"
            disabled={busy}
            onClick={() =>
              start({
                experience,
                research_consent: research,
                analytics_consent: analytics,
              })
            }
          >
            {busy ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : null}
            {resume ? "Continue assessment" : "Start assessment"}
            <ArrowRight aria-hidden="true" />
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
function SessionHome({
  home,
  busy,
  start,
}: {
  home: LearningHome;
  busy: boolean;
  start: (size: number) => void;
}) {
  const [size, setSize] = useState("20");
  const completed = home.recent.filter((item) => item.completed);
  return (
    <>
      <div className="home-layout">
        <section className="home-main">
          <h1 tabIndex={-1}>Your next session.</h1>
          <p className="home-lede">Choose 10, 20, or 30 puzzles.</p>
          <RadioGroup
            aria-label="Session length"
            value={size}
            onValueChange={(value) => setSize(String(value))}
            className="length-options"
          >
            {[
              { value: "10", label: "Quick", detail: "10 puzzles" },
              { value: "20", label: "Standard", detail: "20 puzzles" },
              { value: "30", label: "Extended", detail: "30 puzzles" },
            ].map((item) => (
              <Label
                className="session-option"
                data-selected={size === item.value}
                key={item.value}
                htmlFor={`length-${item.value}`}
              >
                <RadioGroupItem
                  id={`length-${item.value}`}
                  value={item.value}
                  disabled={busy || !!home.active_session}
                />
                <span className="option-text">
                  <strong>{item.label}</strong>
                  <span>{item.detail}</span>
                </span>
                <SquareTrack
                  className="option-track"
                  states={Array.from({ length: Number(item.value) }, () =>
                    size === item.value ? "current" : "upcoming",
                  )}
                />
              </Label>
            ))}
          </RadioGroup>
          <div className="session-picker-footer">
            {home.active_session ? (
              <p>
                {home.active_session.finished_count} of{" "}
                {home.active_session.total} puzzles completed. Your session is
                saved.
              </p>
            ) : null}
            {home.active_session ? (
              <ButtonLink
                size="lg"
                href={`#/session/${home.active_session.id}`}
              >
                Resume session
                <ArrowRight aria-hidden="true" />
              </ButtonLink>
            ) : (
              <Button
                size="lg"
                disabled={busy}
                onClick={() => start(Number(size))}
              >
                Start session
                <ArrowRight aria-hidden="true" />
              </Button>
            )}
          </div>
        </section>
        <aside className="home-standing" aria-label="Your standing">
          <p className="standing-label">Estimated puzzle rating</p>
          <p className="standing-rating">
            {home.profile.puzzle_rating.toLocaleString()}
          </p>
          {home.profile.rating_range ? (
            <p className="standing-note">
              Starting range {home.profile.rating_range[0]}-
              {home.profile.rating_range[1]}
            </p>
          ) : null}
          <dl className="standing-stats">
            <div>
              <dt>Puzzles solved</dt>
              <dd>
                {home.profile.puzzles_solved}
                <small> of {home.profile.puzzles_attempted}</small>
              </dd>
            </div>
          </dl>
          <div className="research-status">
            <strong>
              {home.profile.research_consent
                ? "Research participation on"
                : "Practice at your own pace"}
            </strong>
            <p>
              {home.profile.research_consent
                ? "Thanks for taking part in the study."
                : "Research participation is optional."}
            </p>
            <a href="#/profile" className="text-link">
              Manage your data
              <ChevronRight aria-hidden="true" />
            </a>
          </div>
        </aside>
      </div>
      {home.recent.length > 0 ? (
        <section className="recent-section">
          <div className="section-heading">
            <h2>Recent sessions</h2>
            <a href="#/history" className="text-link">
              View history
              <ArrowRight aria-hidden="true" />
            </a>
          </div>
          <div className="session-list">
            {home.recent.length ? (
              home.recent
                .slice(0, 3)
                .map((item) => <SessionRow item={item} key={item.id} />)
            ) : (
              <div className="history-empty">
                <History aria-hidden="true" />
                <div>
                  <h3>Your first session starts here.</h3>
                  <p>Completed sessions will appear in your history.</p>
                </div>
              </div>
            )}
          </div>
          {completed.length ? (
            <p className="list-footnote">
              Your results include sessions with and without hints.
            </p>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
function HistoryPage({
  page,
  changePage,
}: {
  page: number;
  changePage: (page: number) => void;
}) {
  const api = useApi();
  const [result, setResult] = useState<LearningHistory | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<LearningHistory>(`/learning/history?page=${page}`)
      .then((value) => {
        if (active) setResult(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [api, page]);
  return (
    <>
      <div className="page-intro">
        <h1 tabIndex={-1}>Session history</h1>
        <p>Your puzzles, progress and results.</p>
      </div>
      {error ? (
        <p role="alert" className="error-message">
          {error}
        </p>
      ) : null}
      <Card className="history-card">
        <div className="session-list">
          {result ? (
            result.items.length ? (
              result.items.map((item) => (
                <SessionRow item={item} key={item.id} />
              ))
            ) : (
              <div className="history-empty">
                <History aria-hidden="true" />
                <div>
                  <h3>No sessions yet.</h3>
                  <p>Start a session to build your history.</p>
                  <ButtonLink className="mt-4" href="#/home">
                    Choose a session
                  </ButtonLink>
                </div>
              </div>
            )
          ) : (
            <div className="loading-state" role="status">
              Loading sessions…
            </div>
          )}
        </div>
        {result && result.total > 0 ? (
          <div className="history-pagination">
            <span role="status">
              Page {result.page} of {result.total_pages}
            </span>
            <Pagination aria-label="Session history pages">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href={`#/history?page=${Math.max(1, result.page - 1)}`}
                    aria-disabled={result.page === 1}
                    tabIndex={result.page === 1 ? -1 : 0}
                    onClick={(event) => {
                      event.preventDefault();
                      if (result.page > 1) changePage(result.page - 1);
                    }}
                  />
                </PaginationItem>
                {Array.from(
                  { length: result.total_pages },
                  (_, index) => index + 1,
                )
                  .filter(
                    (value) =>
                      Math.abs(value - result.page) <= 1 ||
                      value === 1 ||
                      value === result.total_pages,
                  )
                  .map((value) => (
                    <PaginationItem key={value}>
                      <PaginationLink
                        isActive={value === result.page}
                        href={`#/history?page=${value}`}
                        onClick={(event) => {
                          event.preventDefault();
                          changePage(value);
                        }}
                      >
                        {value}
                      </PaginationLink>
                    </PaginationItem>
                  ))}
                <PaginationItem>
                  <PaginationNext
                    href={`#/history?page=${result.page + 1}`}
                    aria-disabled={result.page === result.total_pages}
                    tabIndex={result.page === result.total_pages ? -1 : 0}
                    onClick={(event) => {
                      event.preventDefault();
                      if (result.page < result.total_pages)
                        changePage(result.page + 1);
                    }}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        ) : null}
      </Card>
    </>
  );
}
function Countdown({
  puzzle,
  refresh,
}: {
  puzzle: Activity;
  refresh: () => void;
}) {
  const [left, setLeft] = useState(puzzle.remaining_seconds || 0);
  const callback = useRef(refresh);
  callback.current = refresh;
  useEffect(() => {
    const deadline = Date.now() + (puzzle.remaining_seconds || 0) * 1000;
    setLeft(puzzle.remaining_seconds || 0);
    if (puzzle.completed) return;
    let expired = false;
    const interval = window.setInterval(() => {
      const value = Math.max(0, (deadline - Date.now()) / 1000);
      setLeft(value);
      if (value === 0 && !expired) {
        expired = true;
        callback.current();
      }
    }, 500);
    return () => clearInterval(interval);
  }, [puzzle.id, puzzle.remaining_seconds, puzzle.completed]);
  const rounded = Math.ceil(left);
  return (
    <span
      className="puzzle-clock"
      role="timer"
      aria-live="off"
      aria-label={`${rounded} seconds remaining`}
    >
      <Clock3 aria-hidden="true" />
      {Math.floor(rounded / 60)}:{String(rounded % 60).padStart(2, "0")}
    </span>
  );
}
function RatingChoices({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (value: number) => void;
}) {
  const fieldId = useId();
  return (
    <fieldset className="feedback-field">
      <legend>{label}</legend>
      <RadioGroup
        aria-label={label}
        value={value === null ? "" : String(value)}
        onValueChange={(next) => onChange(Number(next))}
        className="rating-choices"
      >
        {[1, 2, 3, 4, 5].map((number) => (
          <Label
            className="rating-choice"
            data-selected={value === number}
            htmlFor={`${fieldId}-${number}`}
            key={number}
          >
            <RadioGroupItem
              id={`${fieldId}-${number}`}
              value={String(number)}
            />
            <span>{number}</span>
          </Label>
        ))}
      </RadioGroup>
      <div className="rating-scale">
        <span>Not at all</span>
        <span>Very much</span>
      </div>
    </fieldset>
  );
}
function LearningPanel({
  id,
  busy,
  perform,
  profile,
  changed,
}: {
  id: string;
  busy: boolean;
  perform: (action: () => Promise<void>) => Promise<void>;
  profile: Profile;
  changed: () => Promise<void>;
}) {
  const api = useApi();
  const [session, setSession] = useState<LearningSession | null>(null);
  const [error, setError] = useState("");
  const [confidence, setConfidence] = useState<number | null>(null);
  const [satisfaction, setSatisfaction] = useState<number | null>(null);
  const [helpfulness, setHelpfulness] = useState<number | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
  }, [
    session?.id,
    session?.completed,
    session?.puzzle.id,
    !!session?.feedback,
  ]);
  const wasComplete = useRef<boolean | null>(null);
  useEffect(() => {
    if (!session) return;
    if (wasComplete.current === false && session.completed) play("complete");
    wasComplete.current = session.completed;
  }, [session?.completed]);
  const latest = useRef<LearningSession | null>(null);
  latest.current = session;
  // Moves are checked locally and posted in order; other actions wait for
  // this queue so they always send the server's current versions.
  const sync = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef(0);
  const reply = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(reply.current), []);
  const refresh = useCallback(async () => {
    const next = await api<LearningSession>(`/learning/${id}`);
    window.clearTimeout(reply.current);
    setError("");
    latest.current = next;
    setSession(next);
    if (next.completed) await changed();
  }, [api, id, changed]);
  useEffect(() => {
    let active = true;
    setSession(null);
    api<LearningSession>(`/learning/${id}`)
      .then((next) => {
        if (active) setSession(next);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [api, id]);
  useEffect(() => {
    setConfidence(null);
  }, [session?.puzzle.id]);
  const puzzle = session?.puzzle;
  useEffect(() => {
    if (!puzzle || (!profile.analytics_consent && !profile.research_consent))
      return;
    const focus = () => {
      api<void>(
        "/interactions",
        jsonRequest({
          activity_id: puzzle.id,
          kind: "focus_changed",
          focused: document.visibilityState === "visible",
        }),
      ).catch(() => {});
    };
    document.addEventListener("visibilitychange", focus);
    return () => document.removeEventListener("visibilitychange", focus);
  }, [api, puzzle?.id, profile.analytics_consent, profile.research_consent]);
  async function action(
    path: string,
    body: Record<string, unknown> | (() => Record<string, unknown>),
  ) {
    await perform(async () => {
      await sync.current;
      try {
        await api<Activity>(
          path,
          jsonRequest(typeof body === "function" ? body() : body),
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) await refresh();
        throw error;
      }
      await refresh();
    });
  }
  // Applies a puzzle change locally, then posts it through the ordered queue.
  // The server's state replaces the local one once the queue drains.
  function optimistic(
    puzzle: Activity,
    path: string,
    body: Record<string, unknown>,
  ) {
    const base = latest.current;
    if (!base) return;
    const finished = puzzle.completed && !base.puzzle.completed;
    const next: LearningSession = {
      ...base,
      puzzle,
      ...(finished
        ? {
            finished_count: base.finished_count + 1,
            solved: base.solved + Number(!!puzzle.solved),
            outcomes: [
              ...base.outcomes,
              {
                solved: !!puzzle.solved,
                hint_used: !!puzzle.hint_shown,
                status: puzzle.status || "",
              },
            ],
          }
        : {}),
    };
    latest.current = next;
    setSession(next);
    pending.current += 1;
    sync.current = sync.current.then(async () => {
      try {
        await api<Activity>(path, jsonRequest(body));
      } catch (e) {
        pending.current = 0;
        await perform(async () => {
          await refresh();
          throw e;
        });
        return;
      }
      pending.current -= 1;
      if (pending.current === 0) await refresh().catch(() => {});
    });
  }
  function submitMove(move: string) {
    const current = latest.current?.puzzle;
    if (!current) return;
    const body = { move, version: current.version, confidence };
    const path = `/puzzles/${current.id}/moves`;
    const local = playLocally(current, move);
    if (!local) {
      action(path, body);
      return;
    }
    optimistic(local.played, path, body);
    const moveSound = (before: Activity, after: Activity, uci: string) =>
      play(
        after.check ? "check" : before.pieces[uci.slice(2, 4)] ? "capture" : "move",
      );
    if (local.played.status === "incorrect") play("missed");
    else {
      moveSound(current, local.played, move);
      if (local.played.solved) play("solved");
    }
    if (local.replied) {
      const { played, replied } = local;
      window.clearTimeout(reply.current);
      reply.current = window.setTimeout(() => {
        const base = latest.current;
        if (base?.puzzle !== played) return;
        const next = { ...base, puzzle: replied };
        if (replied.completed && !played.completed) {
          next.finished_count += 1;
          next.solved += 1;
          next.outcomes = [
            ...next.outcomes,
            { solved: true, hint_used: !!replied.hint_shown, status: "solved" },
          ];
        }
        latest.current = next;
        setSession(next);
        moveSound(played, replied, replied.moves?.at(-1) || "");
        if (replied.solved) play("solved");
      }, 250);
    }
  }
  function showHint() {
    const current = latest.current?.puzzle;
    if (!current || current.completed || current.hint_shown) return;
    const body = { version: current.version };
    const path = `/puzzles/${current.id}/hint`;
    play("hint");
    if (!current.hint_text) return action(path, body);
    optimistic(
      {
        ...current,
        hint_shown: true,
        hint: current.hint_text,
        version: current.version + 1,
      },
      path,
      body,
    );
  }
  function skip() {
    const current = latest.current?.puzzle;
    if (!current || current.completed) return;
    optimistic(
      {
        ...current,
        completed: true,
        solved: false,
        status: "skipped",
        legal_moves: [],
        version: current.version + 1,
      },
      `/puzzles/${current.id}/skip`,
      { version: current.version },
    );
  }
  async function nextPuzzle() {
    await perform(async () => {
      await sync.current;
      const base = latest.current;
      if (!base) return;
      try {
        // /next returns the full session, so no follow-up fetch is needed.
        const next = await api<LearningSession>(
          `/learning/${id}/next`,
          jsonRequest({ version: base.version }),
        );
        window.clearTimeout(reply.current);
        latest.current = next;
        setSession(next);
        if (next.completed) await changed();
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) await refresh();
        throw error;
      }
    });
  }
  if (error)
    return (
      <div className="error-message" role="alert">
        {error}
        <Button variant="outline" onClick={() => perform(refresh)}>
          Retry
        </Button>
      </div>
    );
  if (!session || !puzzle)
    return (
      <div className="loading-state" role="status">
        Loading your puzzle…
      </div>
    );
  const calibration = session.kind === "calibration";
  if (session.completed)
    return (
      <section className="session-complete">
        <div className="completion-summary">
          <h1 tabIndex={-1} ref={titleRef}>
            {calibration ? "Your starting point." : "Session complete."}
          </h1>
          {calibration ? (
            <div className="completion-result">
              <strong className="completion-rating">
                {session.estimated_rating}
              </strong>
              <span>
                Estimated puzzle rating
                <small>
                  Provisional range {session.rating_range[0]}-
                  {session.rating_range[1]}
                </small>
              </span>
            </div>
          ) : (
            <div className="completion-result">
              <strong className="completion-rating">
                {session.solved}
                <small> of {session.total}</small>
              </strong>
              <span>
                Puzzles solved
                <small>
                  {session.outcomes.filter((item) => item.hint_used).length}{" "}
                  with a hint
                </small>
              </span>
            </div>
          )}
          <ul
            className="outcome-strip"
            aria-label={`${session.solved} of ${session.total} puzzles solved`}
          >
            {session.outcomes.map((outcome, index) => (
              <li
                className="track-square"
                data-state={outcome.solved ? "solved" : "missed"}
                style={{ "--index": index } as CSSProperties}
                key={index}
              >
                <span className="sr-only">
                  Puzzle {index + 1}: {outcome.status}
                </span>
                {outcome.solved ? (
                  <Check aria-hidden="true" />
                ) : (
                  <X aria-hidden="true" />
                )}
              </li>
            ))}
          </ul>
          {calibration ? (
            <p className="completion-note">
              Your rating will become more precise as you solve unassisted
              puzzles.
            </p>
          ) : null}
        </div>
        {!calibration && !session.feedback ? (
          <div className="feedback-card">
            <h2>A quick check-in</h2>
            <div>
              <RatingChoices
                label="How satisfied are you with this session?"
                value={satisfaction}
                onChange={setSatisfaction}
              />
              {session.outcomes.some((item) => item.hint_used) ? (
                <RatingChoices
                  label="How helpful were the hints?"
                  value={helpfulness}
                  onChange={setHelpfulness}
                />
              ) : null}
              <div className="feedback-actions">
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() =>
                    action(`/learning/${id}/feedback`, { skipped: true })
                  }
                >
                  Skip feedback
                </Button>
                <Button
                  disabled={busy || satisfaction === null}
                  onClick={() =>
                    action(`/learning/${id}/feedback`, {
                      satisfaction,
                      helpfulness,
                    })
                  }
                >
                  Save feedback
                  <Check aria-hidden="true" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="completion-next">
            <ButtonLink size="lg" href="#/home">
              {calibration ? "Choose your first session" : "Back to sessions"}
              <ArrowRight aria-hidden="true" />
            </ButtonLink>
          </div>
        )}
      </section>
    );
  const title = calibration ? "Find your starting level" : "Puzzle session";
  const total = session.total;
  const ordinal = Math.min(
    total,
    session.finished_count + (puzzle.completed ? 0 : 1),
  );
  return (
    <div className="learning-page">
      <div className="learning-heading">
        <div>
          <a className="text-link" href="#/home">
            <ChevronLeft aria-hidden="true" />
            {calibration ? "Assessment" : "Sessions"}
          </a>
          <h1 tabIndex={-1} ref={titleRef}>
            {title}
          </h1>
        </div>
        <div
          className="session-progress"
          role="progressbar"
          aria-label="Session progress"
          aria-valuenow={session.finished_count}
          aria-valuemin={0}
          aria-valuemax={total}
        >
          <SquareTrack states={sessionStates(session, ordinal - 1)} />
          <span className="session-progress-label" aria-hidden="true">
            {calibration ? "No hints" : `${session.solved} solved`}
          </span>
        </div>
      </div>
      <div className="puzzle-layout">
        <section className="puzzle-board-panel">
          <div className="puzzle-board-header">
            <span>
              Puzzle {ordinal} of {total}
            </span>
            <Countdown puzzle={puzzle} refresh={() => perform(refresh)} />
          </div>
          <Board
            position={puzzle}
            disabled={busy || puzzle.completed}
            orientation={puzzle.player_color || puzzle.turn}
            lastMove={puzzle.moves?.at(-1)}
            resetKey={puzzle.id}
            onMove={submitMove}
            onSelect={(square) => {
              if (profile.analytics_consent)
                api<void>(
                  "/interactions",
                  jsonRequest({
                    activity_id: puzzle.id,
                    kind: "square_selected",
                    square,
                  }),
                ).catch(() => {});
            }}
          />
        </section>
        <aside className="puzzle-instructions">
          <div className="turn-heading">
            <span className={`turn-dot ${puzzle.turn}`} />
            <h2>
              {puzzle.completed
                ? "Position complete"
                : `${puzzle.player_color === "black" ? "Black" : "White"} to move`}
            </h2>
          </div>
          <p className="puzzle-prompt">Find the winning continuation.</p>
          <dl className="puzzle-details">
            <div>
              <dt>Difficulty</dt>
              <dd>
                <HiddenScore
                  key={puzzle.id}
                  label="puzzle difficulty"
                  value={puzzle.rating ?? ""}
                />
              </dd>
            </div>
            <div>
              <dt>Moves played</dt>
              <dd>
                {Math.ceil((puzzle.moves?.length || 0) / 2)} of{" "}
                {puzzle.player_moves_required || 1}
              </dd>
            </div>
          </dl>
          {puzzle.completed ? (
            <div
              className={`puzzle-result ${puzzle.solved ? "is-solved" : "is-missed"}`}
              role="status"
            >
              {puzzle.solved ? (
                <CheckCircle2 aria-hidden="true" />
              ) : (
                <X aria-hidden="true" />
              )}
              <div>
                <strong>
                  {puzzle.solved
                    ? "Solved"
                    : puzzle.status === "skipped"
                      ? "Puzzle skipped"
                      : puzzle.status === "timeout"
                        ? "Time’s up"
                        : "Not quite"}
                </strong>
                <p>
                  {puzzle.solved
                    ? "Ready for the next position?"
                    : "Review the line, then try a new position."}
                </p>
              </div>
            </div>
          ) : (
            <fieldset className="confidence-field">
              <legend>How confident are you?</legend>
              <RadioGroup
                aria-label="Move confidence"
                value={confidence === null ? "" : String(confidence)}
                onValueChange={(value) => setConfidence(Number(value))}
                className="confidence-options"
              >
                {[
                  { value: 25, label: "Low" },
                  { value: 50, label: "Medium" },
                  { value: 75, label: "High" },
                ].map((item) => (
                  <Label
                    key={item.value}
                    htmlFor={`confidence-${item.value}`}
                    data-selected={confidence === item.value}
                  >
                    <RadioGroupItem
                      id={`confidence-${item.value}`}
                      value={String(item.value)}
                    />
                    {item.label}
                  </Label>
                ))}
              </RadioGroup>
              <small>Optional</small>
            </fieldset>
          )}
          {puzzle.hint ? (
            <div className="hint-content">
              <span>
                <Lightbulb aria-hidden="true" />
                Hint
              </span>
              <p>{puzzle.hint}</p>
            </div>
          ) : null}
          {puzzle.completed && puzzle.solution ? (
            <div className="solution-line">
              <span id={`solution-${puzzle.id}`}>Solution</span>
              <ol aria-labelledby={`solution-${puzzle.id}`}>
                {(puzzle.solution_san || puzzle.solution).map((move, index) => (
                  <li key={index} data-side={index % 2 ? "reply" : "player"}>
                    <span className="solution-who">
                      {index % 2 ? "Reply" : "Your move"}
                    </span>
                    <span className="solution-san">{move}</span>
                    {puzzle.solution_san ? (
                      <span className="solution-words">
                        {describeMove(move)}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          <div className="puzzle-actions">
            {puzzle.completed ? (
              <Button
                size="lg"
                disabled={busy}
                onClick={nextPuzzle}
              >
                Next puzzle
                {busy ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : (
                  <ArrowRight aria-hidden="true" />
                )}
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  disabled={
                    busy || !session.hints_available || !!puzzle.hint_shown
                  }
                  onClick={showHint}
                >
                  <Lightbulb aria-hidden="true" />
                  {puzzle.hint_shown ? "Hint shown" : "Get a hint"}
                </Button>
                {!session.hints_available ? (
                  <p className="hint-unavailable">
                    {calibration
                      ? "Hints are off during your assessment."
                      : "This session is without hints."}
                  </p>
                ) : null}
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={skip}
                >
                  Skip puzzle
                  <ChevronRight aria-hidden="true" />
                </Button>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
export function Workspace({
  accountControl,
  signOut,
}: {
  accountControl?: ReactNode;
  signOut: () => Promise<void>;
}) {
  const api = useApi();
  const [route, setRoute] = useState(readRoute);
  const [home, setHome] = useState<LearningHome | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const locked = useRef(false);
  const heading = useRef<HTMLDivElement>(null);
  const reload = useCallback(
    async () => setHome(await api<LearningHome>("/learning")),
    [api],
  );
  useEffect(() => {
    const changed = () => {
      setRoute(readRoute());
      setError("");
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  useEffect(() => {
    let active = true;
    api<LearningHome>("/learning")
      .then((value) => {
        if (active) setHome(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [api]);
  useEffect(() => {
    heading.current?.querySelector<HTMLHeadingElement>("h1")?.focus();
  }, [route.mode]);
  const perform = useCallback(
    async (action: () => Promise<void>) => {
      if (locked.current) return;
      locked.current = true;
      setBusy(true);
      setError("");
      try {
        await action();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not save. Try again.");
        if (e instanceof ApiError && e.status === 409)
          await reload().catch(() => {});
      } finally {
        locked.current = false;
        setBusy(false);
      }
    },
    [reload],
  );
  const navigate = (mode: string, id?: string, page?: number) => {
    location.hash = `/${mode}${id ? "/" + id : ""}${page && page > 1 ? "?page=" + page : ""}`;
  };
  const alert = error ? (
    <div className="error-message" role="alert">
      <span>{error}</span>
      <Button variant="outline" size="sm" onClick={() => perform(reload)}>
        Retry
      </Button>
    </div>
  ) : null;
  if (!home)
    return (
      <PublicLayout>
        {alert}
        <div className="loading-state" role="status">
          <LoaderCircle className="animate-spin size-5" aria-hidden="true" />
          Loading your workspace…
        </div>
      </PublicLayout>
    );
  const profile = home.profile;
  const intro =
    !profile.calibration_complete && !(route.mode === "session" && route.id);
  const panel =
    route.mode === "session" && route.id ? (
      <LearningPanel
        key={route.id}
        id={route.id}
        busy={busy}
        perform={perform}
        profile={profile}
        changed={reload}
      />
    ) : null;
  if (!profile.calibration_complete)
    return (
      <PublicLayout
        control={
          <Button variant="ghost" onClick={() => signOut()}>
            Sign out
          </Button>
        }
      >
        {alert}
        {intro ? (
          <OnboardingIntro
            profile={profile}
            resume={!!home.onboarding_id}
            busy={busy}
            start={(values) =>
              perform(async () => {
                await api<Profile>("/me", jsonRequest(values, "PATCH"));
                const session = await api<LearningSession>("/onboarding", {
                  method: "POST",
                });
                await reload();
                navigate("session", session.id);
              })
            }
          />
        ) : (
          panel
        )}
      </PublicLayout>
    );
  return (
    <AppLayout
      items={navigation}
      active={route.mode === "session" ? "home" : route.mode}
      brandHref="#/home"
      accountControl={accountControl}
      accountName={profile.nickname || "Your account"}
      heading={
        <span className="topbar-label">
          {route.mode === "history"
            ? "History"
            : route.mode === "profile"
              ? "Profile"
              : "Puzzle practice"}
        </span>
      }
      headerControl={
        <div className="header-rating">
          <span aria-hidden="true">Rating</span>
          <span className="sr-only">Puzzle rating</span>
          <strong>{profile.puzzle_rating}</strong>
        </div>
      }
    >
      <div ref={heading}>
        {alert}
        {route.mode === "home" ? (
          <SessionHome
            home={home}
            busy={busy}
            start={(size) =>
              perform(async () => {
                const session = await api<LearningSession>(
                  "/learning/sessions",
                  jsonRequest({ size }),
                );
                await reload();
                navigate("session", session.id);
              })
            }
          />
        ) : route.mode === "history" ? (
          <HistoryPage
            page={route.page}
            changePage={(page) => navigate("history", undefined, page)}
          />
        ) : route.mode === "profile" ? (
          <>
            <div className="page-intro">
              <h1 tabIndex={-1}>Your profile</h1>
              <p>Your preferences and research participation.</p>
            </div>
            <ProfilePage
              profile={profile}
              busy={busy}
              save={(values) =>
                perform(async () => {
                  await api<Profile>("/me", jsonRequest(values, "PATCH"));
                  await reload();
                })
              }
              download={() =>
                perform(async () => {
                  const blob = await api<Blob>("/me/export");
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement("a");
                  link.href = url;
                  link.download = "chesso-records.json";
                  link.click();
                  URL.revokeObjectURL(url);
                })
              }
              remove={() =>
                perform(async () => {
                  await api<void>("/me", { method: "DELETE" });
                  await signOut();
                })
              }
            />
          </>
        ) : (
          panel
        )}
      </div>
    </AppLayout>
  );
}
