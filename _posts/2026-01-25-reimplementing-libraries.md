---
layout: post
title:  "Reimplementing ciso8601 using Claude Code"
date:   2026-01-25 00:00:00 -0500
tags: ai claude ciso8601 rfc3339 rfc9557 simd
---


# The problem

A few years back, I explored the idea of using [SIMD intrinsics to speed up ISO 8601 parsing](https://movermeyer.com/2023-01-04-rfc-3339-simd/). But using intrinsics was a pain since you had to handle all the compilation and CPU detection yourself.

Changes since then:

* RFC 9557 was released, an even simpler version of RFC 3339
  * I found out about it via [this blog post](https://www.zachleat.com/web/adventures-in-date-parsing/)
  * I dreamed about cutting some conditionals from `ciso8601`
* I saw [this blog post](https://atempleton.bearblog.dev/i-made-zig-compute-33-million-satellite-positions-in-3-seconds-no-gpu-required/) showing that you could use Zig to create Python extensions that used Zig's high-level SIMD support
* AI agents exist

I figured that it might be interesting to see if Claude Code could help me implement a new version of `ciso8601`, using Zig and SIMD. (Spoilers: it can; easily)

# The context and prompt

I used [Markdownload](https://addons.mozilla.org/en-CA/firefox/addon/markdownload) to download/store the various blog posts and the specs: [mine](https://movermeyer.com/2023-01-04-rfc-3339-simd/), [the astroz one](https://atempleton.bearblog.dev/i-made-zig-compute-33-million-satellite-positions-in-3-seconds-no-gpu-required/), [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339), and [RFC 9557](https://www.rfc-editor.org/rfc/rfc9557.pdf).
I cloned the related repos into sibling directories: [`ciso8601`](https://github.com/closeio/ciso8601), [`astroz`](https://github.com/ATTron/astroz), and the `simdrfc3339` repo from my previous exploration.

Then I opened `claude` and gave it this prompt:

> I want to create the world's fastest ISO 8601 parser for Python. It'll be faster by only supporting the RFC 9557 subset, and by using Zig's SIMD support. Take a look at `prompts/docs` directory for relevant specs, and blog posts. See the sibling directories for the mentioned git repos.

Within a few minutes, it managed to set up a Zig-based Python extension and some basic tests.

It then built out a basic benchmarking script, and got the first performance numbers: its implementation took 820 ns, more than 20x slower than `ciso8601`'s 35 ns.

# Why is it still slower?

> Let's go faster! Why are you slower than `ciso8601`?

By prompting Claude with this in a loop, it found each of `ciso8601`'s optimizations, and faithfully adapted each to this new repo.

The performance improved, first to 217 ns, and then down to 35 ns. 📉

Within two hours, and for < $20 in tokens, Claude had written a new implementation that had matched the performance as `ciso8601`, using Zig and SIMD instead.

It hadn't invented any new techniques; it had simply, competently adapted the techniques to its implementation.

# Why is it still slower?

I wasn't aiming to match the performance of `ciso8601`, I was hoping to exceed it.

I spent another hour attempting to prompt Claude to go even faster.

However, at this point the runtime was dominated by the creation of the Python `PyDateTime` objects, there simply isn't that much room for improvement.

Claude's assessment:

```
Total: 34-35ns
  ├─ PyDateTime creation: 15-17ns (48%) ← CANNOT OPTIMIZE
  ├─ Zig parser:          5ns     (14%) ← Already optimal
  ├─ Timezone cache:      3ns     (9%)  ← Optimized
  ├─ C↔Zig boundary:      1ns     (3%)  ← Architecture tax
  └─ C API overhead:      9-10ns  (26%) ← Minimal
```

Claude would try some optimization, then despair that it was only shaving 1 ns off the runtime, then revert it, and give up.

It repeatedly asked me to simply accept that there weren't any more major optimization wins to be had.

# Why is it still slower?

For the first time in this process, I opened an IDE and looked at the code.

Despite claiming to be using SIMD, the actual function being exported to Python was the non-SIMD version that it initially wrote. It had written a comment saying that the non-SIMD version was faster, which was not true.

It had also implemented validation of the parsed values in Zig, but this was redundant, since Python itself also does that validation in the `PyDateTime` creation.

With both of these changes, it was finally faster than `ciso8601`.

# What does it mean for software development?

When I shared this story, a friend had this quip:

> So the only reason to post a library on GitHub is to say to people: "Save $20 in tokens by using my library!"?

The world of software is changing.

# Are you going to release it?

Not at this time.