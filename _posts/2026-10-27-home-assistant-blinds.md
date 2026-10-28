---
layout: post
title:  "You can just control blinds"
date:   2026-10-27 16:00:00 -0400
categories: ai claude home-assistant esphome iot
---

Two years ago, I discovered [Home Assistant](https://www.home-assistant.io/) and [ESPHome](https://esphome.io/) as a foundation for IoT devices that aren't terrible spyware.
At the time I had the idea to replay the commands from the remote for my motorized blinds, to be able to open and close the blinds using Home Assistant. I bought a [Sonoff RF Bridge R2](https://sonoff.tech/product/smart-home-security/rf-bridger2/), and flashed it with [ESPHome](https://esphome.io/components/rf_bridge/). I could get the radio device to beep and turn its light on/off, but I couldn't control the blinds.

Today, I plugged the hardware in again and had [Claude Code](https://claude.com/claude-code) take a stab at it. It re-flashed it and got to where I had gotten in < 5 minutes.
But then it figured out what needed doing. The RF Bridge actually has two chips: an ESP8285 that runs ESPHome, and a separate radio microcontroller whose stock firmware only understands simple 24-bit codes. My blinds' remote sends 64-bit codes, so the bridge was only ever hearing the first 24 bits of each one.
Over the course of the hour, it directed me in taking it apart and using another microcontroller to flash [passthrough firmware](https://github.com/mightymos/RF-Bridge-OB38S003) onto the radio chip. That let ESPHome decode and replay the raw signals itself. Then calibration, and voila!: control over the blinds from my phone. 🪟 📱

Seeing my blinds move at a push of a button was a visceral reminder that with AI, "You can just do things". I'm excited for my next project.

<div style="display: flex; gap: 1em; align-items: flex-start;">
  <img style="flex: 0.753; min-width: 0;" src="{{ "/assets/img/blinds_rf_bridge_flashing.jpg" }}" alt="The RF bridge's circuit board, removed from its case and wired to an ESP8266 dev board on a breadboard for flashing the radio chip">
  <img style="flex: 0.462; min-width: 0;" src="{{ "/assets/img/blinds_home_assistant.png" }}" alt="Screenshot of the Home Assistant app on a phone, showing the living room blinds open at 73%">
</div>
