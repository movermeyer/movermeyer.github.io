---
layout: post
title:  "You can just control deck lights"
date:   2026-11-02 04:00:00 -0500
tags: ai claude home-assistant esphome iot cc1101
---

After the success of [this project](https://movermeyer.com/2026-11-02-garage-door-remote/)...

**Q:** What else in my house is radio controlled?
**A:** My deck lights.

The previous owner had put the deck lights on a remote. They look lovely, but I never use them because of the hassle of finding the remote.

![Unmarked remote that turned out to be a GE SunSmart Wireless Timer System, Jasco #15435 remote]({{ "/assets/img/deck_lights_remote.jpg" }}){: width="50%"}

The remote has no markings except the FCC registration ID. Claude was able to find [the registration](https://fccid.io/QOB-GE5399) and extract the relevant details.

It turns out that it uses a frequency (315 MHz) that the [garage door opener radio](https://movermeyer.com/2026-11-02-garage-door-remote/) can handle.

So I had Claude capture the signals from the deck lights remote and replay them.
Now the same device can also toggle the deck lights.
The whole process took < 20 minutes.

![A house at night with its deck and octagonal gazebo lit up by the deck lights. Two hanging egg chairs are visible inside the gazebo.]({{ "/assets/img/deck_lights_gazebo.jpg" }})
