# NFL Game Pass Plugin for XBMC #
by Alex Waite and divingmule
Version: 0.2.0 -- Donald Driver Edition

Before reading any further, please understand that while this plugin does
work, not all features are supported (or fully tested) and it should be
regarded as an alpha release. It may crash, spay your puppy, and/or cause your
oven to not heat to 400° F properly. The plugin is under development, and needs
a whole lot of love.

If you're interested in helping out, just drop us an email or send a pull
request. Patches and (constructive) input are always welcome.

## What is NFL Game Pass? ##

NFL Game Pass is website that allows those of us outside of the US (or with IPs
outside of the US ;-) to watch NFL games. Archives of old games stretch back to
2009, coaches film (22 man view) is available, as is audio from each team's
radio network. Overall, it is a sweet service offered by the NFL for those of
us who must have our American Football fix.

## Is NFL Game Rewind supported? ##

No, but we do have plans to add support soon-ish (possibly as its own add-on).
NFL Game Rewind is a similar service, but is different enough that it's not
trivial to add support.

## Why write a plugin for XBMC? ##

First off, we love XBMC and like consuming media through its interface.
Secondly, while NFL Game Pass does have a nice Flash interface, it's... well...
written in Flash. The client is a resource hog, the interface is frequently
buggy, and it includes a bunch of bells and whistles (social media, for
example) that are simply distracting. We're here to watch a game, nothing else.

## What features are currently supported? ##

By now, most NFL Game Pass features are supported.

 * Archived games from 2009 to 2013
 * Live games (requires Gotham)
 * NFL Network - Live (requires Gotham)
 * NFL Total Access
 * Sound FX
 * NFL Gameday
 * NFL RedZone
 * Playbook
 * A Football Life

Currently unsupported features:
 * Condensed game streams
 * Alternate team audio
 * Coaches film (22 man view)
 * Superbowl Archives
 * Top 100 Players
 * Coaches Show
 * NFL Films Presents

## Release names ##

Want a release to be named after your player/coach of choice? Contribute to the
project in some way (code, art, debugging, beer, brazen -- yet effective
-- flattery), and we'll gladly name a future release after them.

## Roadmap ##

A rough roadmap follows:

* Continue work towards feature completeness
* Work on a Game Rewind branch -- this work will determine whether Game Rewind
  needs to be its own add-on, and (if so) how much code can be shared between
  the two add-ons (and refactor the code to accomodate).
* Once Game Rewind support is in master and reasonably stable, begin work on a
  "skin" branch to convert the addon(s) to a "skin" plugin. This will allow us
  much more control over the UI. It should be prettier (more graphics) and more
  intutive.
