# NFL Game Pass/Rewind XBMC Plugin #
**version 0.3.1 — Vince Lombardi Edition** by Alex Waite and divingmule

Before reading any further, please understand that while this plugin does
work, not all features are supported (or fully tested) and it should be
regarded as an alpha release. It may crash, spay your puppy, and/or cause your
oven to not heat to 400° F properly. The plugin is under development, and needs
a whole lot of love.

If you're interested in helping out, just drop us an email or send a pull
request. Patches and (constructive) input are always welcome.

## Any Dependencies? ##
Until this addon is part of an official XBMC repository, dependencies will not
be installed automatically.
 * xmltodict (mirrors.xbmc.org/addons/frodo/script.module.xmltodict/)
 * plugin.cache (just install the YouTube addon, which uses it)

## What is NFL Game Pass? ##

NFL Game Pass is website that allows those of us outside of the US (or with IPs
outside of the US ;-) to watch NFL games. Archives of old games stretch back to
2009, coaches film (22 man view) is available, as is audio from each team's
radio network. Overall, it is a sweet service offered by the NFL for those of
us who must have our American Football fix.

## What is NFL Game Rewind? ##

NFL Game Rewind is very similar to Game Pass, but doesn't have quite as many
features. For example, it does not support live games.

## Why write a plugin for XBMC? ##

First off, we love XBMC and like consuming media through its interface.
Secondly, while there is a nice Flash interface, it's... well...
written in Flash. The client is a resource hog, the interface is frequently
buggy, and it includes a bunch of bells and whistles (social media, for
example) that are simply distracting. We're here to watch a game, nothing else.

## What features are currently supported? ##

By now, most core features are supported.

 * Archived games from 2011 to 2013
 * Condensed games
 * Live games (requires Gotham)
 * NFL Network - Live (requires Gotham)
 * NFL Total Access
 * Sound FX
 * NFL Gameday
 * NFL RedZone
 * Playbook
 * A Football Life
 * NFL Films Presents

Currently unsupported features:
 * Archived games prior to 2011
 * Alternate team audio
 * Coaches film (22 man view)
 * Superbowl Archives
 * Top 100 Players
 * Coaches Show

## Release names ##

Want a release to be named after your player/coach of choice? Contribute to the
project in some way (code, art, debugging, beer, brazen — yet effective —
flattery, etc), and we'll gladly name a future release after them.

## Roadmap ##

A rough roadmap follows:

* Continue work towards feature completeness
* Stabilize Game Rewind support
* Refactor code to be more XBMC agnostic
* Work on a "skin" branch to convert the addon(s) to a "skin" plugin. This will
 allow us much more control over the UI. It should be prettier (more graphics)
 and more intutive.
