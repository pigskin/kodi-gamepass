import xbmcaddon

addon = xbmcaddon.Addon()
subscription = addon.getSetting('subscription')
if subscription == '0':
    from resources import gamepass
else:
    from resources import gamerewind
