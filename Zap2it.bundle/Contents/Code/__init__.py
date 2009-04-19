from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *


import re, string, datetime, time, calendar

PLUGIN_PREFIX = '/video/zap2it'
PROVIDER_INDEX = 'http://tvlistings.zap2it.com/tvlistings/ZCGrid.do?aid=zap2it&isDescriptionOn=true'
DAY = 86400
CACHE_TIME = DAY
EPOCH_DAY = 719162
####################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L('Zap2it'))
  
  Plugin.AddViewGroup('Details', viewMode='InfoList', mediaType='items')
  Plugin.AddViewGroup('EpisodeList', viewMode='Episodes', mediaType='items')
  
  MediaContainer.title1 = L('Zap2it')
  MediaContainer.viewGroup = 'EpisodeList'
  MediaContainer.art = R('art-default.jpg')
  
  HTTP.SetCacheTime(CACHE_TIME)
  
####################################################################################################

def CreateDict():
  Dict.Set('channels', list())
  Dict.Set('postalCode', '')
  Dict.Set('provider', '')
  Dict.Set('timeFormat', '24')
  Dict.Set('inProgress', True)
  Dict.Set('shows', dict())
  
####################################################################################################

def UpdateCache():
  # Get TV Page
  if Dict.Get('postalCode') == '' or Dict.Get('provider') == '' or Dict.Get('timeFormat') == '':
    return
  now = getCurrentTimeSlot()
  
  shows = Dict.Get('shows')
  if shows == None:
    Dict.Set('shows', dict())
    shows = Dict.Get('shows')
    
  for slot in range(now, now + DAY, 3 * 3600):
    grabListings(slot, shows)

####################################################################################################

# TODO: Fix 12hour time (12:30AM vs 12:30PM) in subtitle
# TODO: Ability to show/hide channels
# TODO: Add day to non-today menus

def MainMenu():
  dir = MediaContainer()
  
  if Dict.Get('postalCode') != '' and Dict.Get('provider') != '' and Dict.Get('timeFormat') != '':
    nextTime = getCurrentTimeSlot()
    Plugin.AddPathRequestHandler(PLUGIN_PREFIX, TVMenu, "", "", "")
    
    for k in range(6):
      dir.Append(DirectoryItem(nextTime, timeToDisplay(nextTime), '',''))
      nextTime = nextTime + 1800
        
  dir.Append(Function(DirectoryItem(settingsMenu, title=L('Settings'))))
  return dir

####################################################################################################

def timeToSeconds(t):
  (timeOfDay, meridian) = t.split(' ')
  (hour, minute) = timeOfDay.split(':')
  if meridian == 'PM':
    timeSeconds = 43200
    if hour == 12: hour = 0
  else:
    timeSeconds = 0
  
  if time.daylight != 0:
    timeSeconds = timeSeconds + time.altzone 
  else:
    timeSeconds = timeSeconds + time.timezone  
  
  timeSeconds = timeSeconds + int(minute) * 60 + int(hour) * 3600
  
  timeSeconds = timeSeconds + (datetime.date.toordinal(datetime.datetime.today()) - EPOCH_DAY) * DAY


  #timeSeconds = timeSeconds % DAY # Adjust to time since midnight local time
  return timeSeconds
  
  
def timeToDisplay(t):
  # Adjust to local time
  if time.daylight != 0:
    t = t - time.altzone 
  else:
    t = t - time.timezone
    
  t = t % DAY  
  hour = (t // 3600) % 24
  minute = (t % 3600) // 60
  #Log(str(hour) + ':' + str(minute))
  if Dict.Get('timeFormat') == '12':
    if hour >= 12:
      meridian = 'PM'
    else:
      meridian = 'AM'
    if hour > 12:
      hour = hour - 12
    if hour == 0:
      hour = 12
    
  else:
    meridian = ''
    
  return str(hour) + ':' + str(minute).zfill(2) + ' ' + meridian

def getCurrentTimeSlot():
  now = calendar.timegm(time.gmtime())
  now = now - (now % 1800)
  return now

####################################################################################################

def settingsMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Settings')
  dir.Append(Function(SearchDirectoryItem(setPostalCode, title='ZIP or Postal Code', prompt='Enter your ZIP or Postal Code')))
  if Dict.Get('postalCode') != '':
    dir.Append(Function(PopupDirectoryItem(providerMenu, title='Provider')))
    
  dir.Append(Function(PopupDirectoryItem(timeFormatMenu, title='Time Format')))
  dir.Append(Function(PopupDirectoryItem(inProgressMenu, title='Shows in progress')))
  return dir
  
def setPostalCode(sender, query):
  query = string.join(query.split(' '),'') # No spaces please
  Dict.Set('postalCode', query)

def providerMenu(sender):
  dir = MediaContainer()
  url = 'http://tvlistings.zap2it.com/tvlistings/ZBChooseProvider.do?zipcode=' + Dict.Get('postalCode') + '&method=getProviders'
  providers = XML.ElementFromString(HTTP.Request(url=url, cacheTime=CACHE_TIME), True).xpath('//a[starts-with(@href, "ZCGrid.do?method=decideFwdForLineup")]')
  for provider in providers:
    dir.Append(Function(DirectoryItem(setProvider, title=provider.text)))
  return dir
  
def setProvider(sender):
  Log(sender.itemTitle)
  url = 'http://tvlistings.zap2it.com/tvlistings/ZBChooseProvider.do?zipcode=' + Dict.Get('postalCode') + '&method=getProviders'

  setProviderURL = XML.ElementFromString(HTTP.Request(url=url, cacheTime=CACHE_TIME), True).xpath('//a[text() = "' + sender.itemTitle + '"]')[0].get('href')
  Dict.Set('provider', re.search(r'lineupId=(.*)', setProviderURL).group(1))


def timeFormatMenu(sender):
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(setTimeFormat, title='12 hour')))
  dir.Append(Function(DirectoryItem(setTimeFormat, title='24 hour')))
  return dir

def setTimeFormat(sender):
  timeFormat = re.match(r'(\d\d).*', sender.itemTitle).group(1)
  Dict.Set('timeFormat', timeFormat)


def inProgressMenu(sender):
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(setInProgress, title='Show')))
  dir.Append(Function(DirectoryItem(setInProgress, title='Hide')))
  return dir

def setInProgress(sender):
  if sender.itemTitle == 'Show':
    Dict.Set('inProgress', True)
  else:
    Dict.Set('inProgress', False)
  
####################################################################################################

def grabListings(t, shows):
  url = PROVIDER_INDEX + '&zipcode=' + Dict.Get('postalCode') + '&lineupId=' + Dict.Get('provider') + '&fromTimeInMillis=' + str(t) + '000'
  for td in GetXML(url, True).xpath('//td[starts-with(@class,"zc-pg")]'):
    try: showName = td.xpath('child::a')[0].text.encode('ascii','ignore')
    except: showName = ''
    try: description = td.xpath('child::p')[0].text.encode('ascii','ignore')
    except: description = ''
    
    if (showName != '' or description != ''):
      channel = td.xpath('parent::*')[0].xpath('child::td[@class="zc-st"]')[0]
      channelNum = channel.xpath('descendant::span[@class="zc-st-n"]')[0].text
      channelName = channel.xpath('descendant::span[@class="zc-st-c"]')[0].text
      
      try:
        releaseYear = td.xpath('child::span[@class="zc-pg-y"]')[0].text
        showName = showName + ' ' + releaseYear
      except: pass
      try:
        episodeName = td.xpath('child::span[@class="zc-pg-e"]')[0].text
        description = episodeName + '\n\n' + description
      except: pass
      
      startTime = int(re.search(r'(?:([^,]+),)*', td.get('onclick')).group(1)) // 1000
      startSlot = startTime - (startTime % 1800)
      duration = int(re.search(r'(\d+)', td.get('style')).group(0)) * 15 # seconds
      endTime = startTime + duration
      endSlot = endTime - (endTime % 1800)
      
      if not startSlot in shows: shows[startSlot] = list()
      shows[startSlot].append(dict(title=showName, channel=channelNum + ' ' + channelName, start=startTime, end=endTime, summary=description, inProgress=False))
      for slot in range(startSlot, endSlot, 1800):
        if not slot in shows: shows[slot] = list()
        shows[slot].append(dict(title=showName, channel=channelNum + ' ' + channelName, start=startTime, end=endTime, summary=description, inProgress=True))

####################################################################################################

def TVMenu(pathNouns, path):
  dir = MediaContainer()
  dir.viewGroup = 'Details'
  menuTime = int(pathNouns[0])
  dir.title2 = timeToDisplay(menuTime)
  
  Log(menuTime)
  listings = Dict.Get('shows')
  if not menuTime in listings:
    grabListings(menuTime, listings)
  listings = listings[menuTime]
  
  displayInProgress = Dict.Get('inProgress')
  for listing in listings:
    timeString = timeToDisplay(listing['start']) + ' - ' + timeToDisplay(listing['end'])
    if displayInProgress or not listing['inProgress']:
      dir.Append(Function(DirectoryItem(noMenu, title=listing['title'], subtitle=listing['channel'] + ' ' + timeString, summary=listing['summary'])))

  return dir
  
####################################################################################################

def noMenu(sender):
  pass

####################################################################################################

def GetXML(theUrl, use_html_parser=False):
  return XML.ElementFromString(HTTP.Request(url=theUrl, cacheTime=CACHE_TIME), use_html_parser)

####################################################################################################
