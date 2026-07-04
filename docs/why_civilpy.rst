Why CivilPy — A Shared Toolkit for the Engineering Community
===========================================================

CivilPy is an open, community-owned library of civil and structural
engineering tools. It is written for practicing engineers, but the ideas
behind *how* it is built are just as important as the calculations it
performs. This page explains what CivilPy is, why it lowers the cost of good
design, and how it borrows a handful of proven practices from the software
world to make engineering tools faster to update, easier to trust, and open
for everyone to contribute to.

It is written for three audiences in particular:

* **The National Steel Bridge Alliance (NSBA) and the steel community**, who
  benefit directly from tools that make efficient steel design the path of
  least resistance.
* **Standards-writing organizations**, who set the rules the profession
  designs to and who need those rules reflected quickly and consistently in
  the tools engineers actually use.
* **Colleges and universities**, who prepare the next generation of engineers
  and who can now teach with the same open tools their students will carry
  into practice.

If most of your career has been spent in front of design software rather than
inside it, that is exactly the reader this page is written for. No prior
software background is assumed.


The problem CivilPy is solving
------------------------------

Most engineering calculations are performed the same way they were decades
ago: a spreadsheet built by one engineer, checked by another, and then quietly
copied from project to project. Every firm rebuilds the same beam check, the
same load combination, the same scour calculation — and every copy drifts a
little further from the last. When a specification changes, there is no single
place to update. There is no easy way to know which spreadsheet on which
server reflects the current code and which one is three revisions behind.

This is expensive. It is expensive in the hours spent rebuilding tools that
already exist somewhere. It is expensive in the review time spent re-verifying
math that was already verified last year. And it is expensive in the quiet
inefficiencies that creep into designs when the tool an engineer happens to
have is not quite the best tool for the job.

CivilPy replaces that scattered collection of private spreadsheets with a
single, shared, openly reviewed toolkit — one place where a calculation is
written once, checked continuously, and improved by the whole community
instead of re-invented by each firm.


Better for steel: making efficient design the easy path
-------------------------------------------------------

Steel rewards good engineering. A well-proportioned plate girder, a tuned
bolted field splice, an optimized framing plan — these save real tonnage and
real money. But that efficiency depends on the engineer having good tools
close at hand. When the easiest available tool is a conservative rule of thumb
or an aging spreadsheet, designs drift toward *safe but heavy* simply because
the better calculation was too much trouble to set up.

CivilPy is built to make the efficient path the *convenient* path:

* **Design checks that match the specification.** Steel member and
  connection checks are written directly against the governing provisions, so
  the engineer spends time on judgment, not on re-deriving the code.
* **Consistency across firms and projects.** When two engineers in two
  different offices run the same check, they get the same answer. Reviewers
  can trust the tool instead of re-deriving it, which shortens review and
  frees time for the parts of design that actually need human judgment.
* **Room to optimize.** Because the calculations are fast, transparent, and
  scriptable, it becomes practical to study several framing options instead of
  settling for the first one that works. More options explored means lighter,
  more efficient steel.

For NSBA, this is a direct lever on the outcomes the alliance cares about:
lower-cost, more competitive, more consistently efficient steel bridges,
achieved not by asking engineers to work harder but by putting better tools in
their hands for free.


Better for standards organizations: rules that reach the field quickly
----------------------------------------------------------------------

Today there is a long, quiet gap between the moment a specification is
published and the moment it is faithfully reflected in the tools engineers use
every day. Each firm updates its own spreadsheets on its own schedule, if at
all. The result is a profession that is always designing to a slightly
different mix of code editions.

Because CivilPy is a single shared toolkit, a specification change can be made
*once*, in the open, and flow out to every user through a normal update. And —
this is the part worth dwelling on — every calculation ships with an automatic
set of self-checks that run whenever anything changes (described in plain
terms in the next section). A standards body can see, publicly, that the tool
still produces the expected answers for a set of worked examples. The gap
between "the code says" and "the tool does" shrinks from years to days, and it
shrinks *visibly*.

This also gives standards organizations a new kind of feedback. When the
provisions are expressed as working, testable code, ambiguities that would
otherwise surface as a hundred private emails instead surface as a single,
public, well-documented question — one that everyone with a stake can see and
weigh in on.


Better for education: teaching with the tools of practice
---------------------------------------------------------

Students today often learn on one set of tools and then re-learn everything on
whatever their first employer happens to license. CivilPy is free and open,
which means a university can teach with the *exact* toolkit students will use
in practice — and students can keep using it the day they graduate, with no
license to lose.

Because every calculation is open and readable, CivilPy is also a teaching
text in its own right. A student can follow a design check from the governing
equation all the way to the answer, see the intermediate values, and
understand *why* a member passes or fails rather than trusting a black box.
And because the whole project is developed in the open, a class can do
something that was never before possible: watch a real engineering tool being
built and maintained, and even contribute a fix or a new check as a genuine
piece of coursework that lives on in a tool the profession actually uses.


The quiet advantage: how CivilPy is built
------------------------------------------

Everything above rests on a handful of practices borrowed from modern software
development. These practices are ordinary in the software world and almost
unknown in engineering practice — and they are the real reason CivilPy can be
updated faster, trusted more, and improved by more people than any private
spreadsheet ever could. The terms are introduced only so you recognize them
later; what matters is what each one *does for you*.

A shared logbook that never closes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consider how a change to a design tool happens today. Someone notices a
problem — a check that is too conservative, a provision that was missed, a new
feature the group needs. That concern waits for the next committee meeting.
Not everyone with a stake can attend. Notes are taken, or they are not.
Decisions are made by whoever happened to be in the room, and the engineers
who will actually use the tool often hear about it much later, secondhand.

CivilPy replaces the infrequent meeting with an **always-open, public
logbook**. Anyone — an engineer at any firm, a professor, a student, a
reviewer at a standards body — can write down a bug, a feature request, or a
question, and it stays there, visible to everyone, until it is resolved. The
discussion happens in writing, in the open, where anyone who cares can read the
reasoning and add to it, on their own schedule, whether or not they could make
a meeting. Nothing important depends on being in the room at the right hour.

Think of it as the difference between a decision made in a hallway conversation
and one made in a written record that the whole profession can see, search, and
build on.

Track-changes for engineering tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Word processors have a "track changes" feature that records who changed what,
when, and why, and lets you roll back to any earlier version. CivilPy uses the
same idea for engineering calculations, through a tool called **version
control** (specifically, *git*).

Every single change to every calculation is recorded, permanently, with a note
explaining why it was made and who made it. If a check is ever found to be
wrong, you can see exactly when the error was introduced, what it affected, and
what the tool did before and after. Nothing is ever silently overwritten.
There is no mystery about which version is current, because there is only ever
one authoritative version, and its entire history is open for anyone to
inspect.

For a profession that lives and dies by the quality of its checking and
documentation, this is simply a better record than a folder full of
``beam_check_final_v3_REALfinal.xlsx`` files.

An assembly line that re-checks every change
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the practice usually called **CI/CD**. The name is unimportant; the
behavior is what matters.

Every time anyone proposes a change to CivilPy — no matter how small — an
automatic process springs into action behind the scenes. It re-runs a large
library of worked examples and confirms that every calculation still produces
the answer it is supposed to. If a change would break something, the change is
flagged and stopped *before* it ever reaches a user. If everything still
checks out, the update is packaged and published automatically, along with
this very documentation.

Picture a tireless checker who, every time even a single number is touched,
instantly re-verifies the entire manual of worked examples and refuses to let
anything out the door until it all passes. That is what runs behind CivilPy,
continuously, for free. It is why updates can be frequent *and* safe: the
safety net is automatic, so improvements do not have to wait for a slow,
manual, once-a-year verification cycle.

This is also why a specification update or a new steel check can move from idea
to the engineer's desktop in days rather than years, without anyone having to
choose between "fast" and "trustworthy."


What this adds up to
--------------------

Put the pieces together and the value proposition is straightforward:

* **Lower design cost**, because the profession builds each tool once instead
  of a thousand times, and because reviewers can trust a shared, continuously
  checked calculation instead of re-verifying a private one.
* **More consistently efficient designs**, because the efficient calculation is
  always the convenient one, and because everyone is working from the same
  authoritative tool.
* **Faster, safer updates**, because an automatic safety net lets improvements
  ship continuously without waiting on infrequent manual review.
* **Genuine transparency and inclusion**, because feature requests, bugs, and
  design decisions live in an open, permanent, written record that everyone
  with a stake can see and shape — not in a meeting that not everyone can
  attend.

CivilPy is not asking the profession to become software developers. It is
quietly bringing a few of the software world's best habits — a shared record,
a complete history, and an automatic safety net — to the everyday work of
civil and structural engineering, and offering the result to the whole
community, openly and for free.

How to get involved
-------------------

* **Try it.** ``pip install civilpy`` and work through the examples in the
  :doc:`API reference <civilpy>`.
* **Raise an issue.** If a check is missing, wrong, or too conservative, open
  an issue on the project's GitLab page. That is the always-open logbook
  described above, and every contribution to it is welcome.
* **Contribute.** See the project's ``CONTRIBUTING`` guide. Whether you are a
  practicing engineer, a standards-body reviewer, a professor, or a student, a
  clear worked example or a single corrected check is a real and lasting
  contribution to the profession.
