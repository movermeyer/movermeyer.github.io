---
layout: post
title:  "Genmitsu Sainsmart 3018 PROver CNC debugging"
date:   2022-02-05 12:00:00 -0000
categories: genmitsu sainsmart 3018 prover cnc debugging
---

I recently purchased a [Genmitsu Sainsmart 3018 PROver CNC machine](https://www.sainsmart.com/products/sainsmart-genmitsu-cnc-router-3018-prover-kit), with a GRBL v1.1 control board. I've spent more time then I'd care to admit on simple, silly things. So I'll be documenting them here for my posterity. Hopefully this can help you on your CNC journey.

## Table of Contents <!-- omit in toc -->

- [I can connect to the controller via USB, but cannot jog the spindle](#i-can-connect-to-the-controller-via-usb-but-cannot-jog-the-spindle)
- [I can connect to the controller via USB, but only when the 24V switch is off](#i-can-connect-to-the-controller-via-usb-but-only-when-the-24v-switch-is-off)

## I can connect to the controller via USB, but cannot jog the spindle

24V power isn't getting to the spindle motors / control board.

1. Check that the 24V power adapter is plugged into the wall.
2. Check that the green LED on the power adapter is lit up.
    * If not, unplug the adapter from the wall for a few seconds, then plug it back in.
    * The LED can go out if you have a power surge (In my case, after crashing the spindle into the stock 😅).
3. Check that the 24V spindle power plug is fully plugged into the controller.
    * And that the red power light is lit up on the controller.

## I can connect to the controller via USB, but only when the 24V switch is off

1. Check to ensure that the emergency stop button wasn't bumped.
    * Twist the button clockwise a quarter turn to allow it to pop out.
