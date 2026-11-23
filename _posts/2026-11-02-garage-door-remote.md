---
layout: post
title:  "You can just open garages"
date:   2026-11-02 00:00:00 -0500
categories: ai claude home-assistant esphome iot
---

After the success of [this project](https://movermeyer.com/2026-10-27-home-assistant-blinds/)...

**Q:** What else in my house is radio controlled?
**A:** My garage door opener.

Asking Claude, it seemed very insistent that I buy a device like the [ratgdo](https://ratcloud.llc/), and physically wire it to the opener, bypassing the existing button or remotes. But I didn't want to change the physical infra of the house, if possible. If I end up moving, I don't want there to be anything I need to teach the next owners about IoT devices. And besides, I had only thought of this project because it was remote-controlled.

I looked up the frequency used by my garage door opener (390 MHz) and bought [a radio chip](https://www.amazon.ca/ECSiNG-Wireless-Transceiver-Compatible-Arduinos/dp/B0DS1V77BC) that can do that. I figured that Claude should be able to do something with it.

Claude one-shot the code, and also gave me instructions for which pins to connect between the microcontroller and the radio board. I had a new garage door remote!

![An ESP32 dev board on a breadboard, connected by jumper wires to a CC1101 radio transceiver board with an antenna. My new garage remote. Ignore the mess of wires 🙈]({{ "/assets/img/garage_remote_breadboard.jpg" }})

However, it didn't work right away: pairing the remote with the opener gave 2 flashes (short-long), and then anytime the button was pressed it would flash 3 times, and ignore all presses for the next 30 seconds.

During the debugging, to rule out problems in the transmitting code, I asked it to temporarily impersonate the original remote, which triggered a downgrade from Opus 5.5 for running afoul of cyber safeguards. But Opus 4.8 was more than capable enough to help. Impersonating the original remote caused it to work perfectly, which meant that the code worked.

It turned out that the garage door opener only accepts remote IDs that are even, and the random generator had happened to produce one that was odd. 🫠

Voila! With no knowledge of hardware, I was able to get Claude to talk me through building a new garage door remote hooked up to Home Assistant. The whole process took ~2 hours.
