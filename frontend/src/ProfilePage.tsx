import { useState } from "react";
import { Download, ShieldCheck, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ChoiceSelect } from "./ChoiceSelect";
import type { Profile } from "./types";

export function ProfilePage({
  profile,
  busy,
  save,
  download,
  remove,
}: {
  profile: Profile;
  busy: boolean;
  save: (values: Partial<Profile>) => void;
  download: () => void;
  remove: () => void;
}) {
  const [nickname, setNickname] = useState(profile.nickname);
  const [experience, setExperience] = useState(profile.experience);
  const [analytics, setAnalytics] = useState(profile.analytics_consent);
  const [research, setResearch] = useState(profile.research_consent);
  const [deleting, setDeleting] = useState(false);
  return (
    <div className="profile-grid">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Both fields are optional.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save({
                nickname,
                experience,
                analytics_consent: analytics,
                research_consent: research,
              });
            }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <Label htmlFor="nickname">Display name</Label>
              <Input
                id="nickname"
                maxLength={40}
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="Display name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="experience">Chess experience</Label>
              <ChoiceSelect
                id="experience"
                value={experience}
                onValueChange={(value) =>
                  setExperience(value as Profile["experience"])
                }
                options={[
                  { value: "unspecified", label: "Prefer not to say" },
                  { value: "new", label: "Learning the rules" },
                  { value: "casual", label: "Casual player" },
                  { value: "club", label: "Club player" },
                  { value: "advanced", label: "Advanced player" },
                ]}
              />
            </div>
            <div className="consent-choice">
              <Checkbox
                id="analytics"
                checked={analytics}
                onCheckedChange={(v) => setAnalytics(v === true)}
              />
              <div>
                <Label htmlFor="analytics">
                  Share optional interaction data
                </Label>
                <p>
                  Record selected board squares and whether the tab is in focus.
                  Turning this off also deletes previously saved optional
                  interaction events.
                </p>
              </div>
            </div>
            <div className="consent-choice">
              <Checkbox
                id="research"
                checked={research}
                onCheckedChange={(v) => setResearch(v === true)}
              />
              <div>
                <Label htmlFor="research">
                  Use my puzzle records for research
                </Label>
                <p>
                  Include my moves, confidence, hints, timing, focus changes and
                  session feedback in research under a participant code. Turning
                  this off excludes my records from future research exports.
                </p>
              </div>
            </div>
            <Button disabled={busy} type="submit">
              Save preferences
            </Button>
          </form>
        </CardContent>
      </Card>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <ShieldCheck className="size-6 text-primary" />
            <CardTitle>Data & privacy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm leading-relaxed">
            <p>
              Puzzle attempts, moves, hints and progress are saved to your
              account.
            </p>
            <p>
              Interaction tracking and research participation are optional. You
              can change either preference at any time.
            </p>
            <p>
              Download your profile and all saved records, or delete your Chesso
              data. Your sign-in account will remain available.
            </p>
            <Button
              className="w-full"
              variant="outline"
              disabled={busy}
              onClick={download}
            >
              <Download />
              Download my data
            </Button>
            <Button
              className="w-full"
              variant="ghost"
              disabled={busy}
              onClick={() => setDeleting(true)}
            >
              <Trash2 />
              Delete my Chesso data
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="profile-stats">
              <div>
                <dt>Estimated puzzle rating</dt>
                <dd>{profile.puzzle_rating}</dd>
              </div>
              <div>
                <dt>Solved / attempted</dt>
                <dd>
                  {profile.puzzles_solved} / {profile.puzzles_attempted}
                </dd>
              </div>
              <div>
                <dt>Sessions</dt>
                <dd>{profile.activity_counts.puzzle_session || 0}</dd>
              </div>
            </dl>
            <p className="mt-4 text-xs text-muted-foreground">
              This rating estimates your puzzle level and updates with
              unassisted results.
            </p>
          </CardContent>
        </Card>
      </div>
      <Dialog open={deleting} onOpenChange={setDeleting}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete your Chesso data?</DialogTitle>
            <DialogDescription>
              This permanently removes your Chesso profile and all saved
              records. You will be signed out. Your sign-in account remains
              available.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleting(false)}>
              Keep my data
            </Button>
            <Button variant="destructive" disabled={busy} onClick={remove}>
              Delete my data
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
