from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *

import re, string, datetime, time, calendar, pickle, operator

PLUGIN_PREFIX = '/video/zap2it'
DAY_PREFIX = PLUGIN_PREFIX + '/day'
SEARCH_PREFIX = PLUGIN_PREFIX + '/search'
PROVIDER_INDEX = 'http://tvlistings.zap2it.com/tvlistings/ZCGrid.do?aid=zap2it&isDescriptionOn=true'
SEARCH_INDEX = 'http://tvlistings.zap2it.com/tvlistings/ZCSearch.do?searchType=simple&searchTerm='
SHOW_INDEX = 'http://tvlistings.zap2it.com'
DAY = 86400
CACHE_TIME = DAY

# art-default from http://www.flickr.com/photos/kchrist/117806012
# licensed as CC Attribution-Noncommercial 2.0 Generic

####################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L('Zap2it'), 'icon-default.gif', 'art-default.jpg')
  
  Plugin.AddViewGroup('Details', viewMode='InfoList', mediaType='items')
  Plugin.AddViewGroup('EpisodeList', viewMode='Episodes', mediaType='items')
  
  MediaContainer.title1 = L('Zap2it')
  MediaContainer.viewGroup = 'EpisodeList'
  MediaContainer.art = R('art-default.jpg')
  
  HTTP.SetCacheTime(CACHE_TIME)
  
####################################################################################################

def CreateDict():
  Dict.Set('shows', dict())
  
def CreatePrefs():
  addPref('channels', 'text', dict(), L('Channels')) # dict
  addPref('postalCode', 'text', '', L('Postal Code'))
  addPref('provider', 'text', '', L('Provider'))
  addPref('timeFormat', 'text', '24', L('Time Format'))
  addPref('collapseShows', 'text', False, L('Collapse Shows'))
  addPref('inProgress', 'text', True, L('In Progress')) # bool
  addPref('favourites', 'text', list(), L('Favourites')) # list
  
####################################################################################################

def UpdateCache():
  # Get TV Page
  if getPref('postalCode') == '' or getPref('provider') == '' or getPref('timeFormat') == '':
    return
  now = getCurrentTimeSlot()
  
  shows = Dict.Get('shows')
  if shows == None:
    Dict.Set('shows', dict())
    shows = Dict.Get('shows')
    
  for slot in range(now, now + DAY, 3 * 3600):
    grabListings(slot, shows)

  channels = getPref('channels')
  if type(channels) != type(dict):
    channels = dict()

  url = PROVIDER_INDEX + '&zipcode=' + getPref('postalCode') + '&lineupId=' + getPref('provider')
  for td in GetXML(url, True).xpath('//td[starts-with(@class,"zc-st")]'):
    channelNum = int(td.xpath('descendant::span[@class="zc-st-n"]')[0].text)
    channelName = td.xpath('descendant::span[@class="zc-st-c"]')[0].text
    if not channelNum in channels:
      channels[channelNum] = dict(name=channelName, enabled=True)
      
  setPref('channels', channels)
      

####################################################################################################

# TODO: Add day to non-today menus
# TODO: Link to saved folder
# TODO: Clean old time slots from dictionary
# TODO: Translate times to 24hr in search results

def MainMenu():
  dir = MediaContainer()
  dir.nocache = 1
  
  if getPref('postalCode') != '' and getPref('provider') != '' and getPref('timeFormat') != '':
    nextTime = getCurrentTimeSlot()
    Plugin.AddPathRequestHandler(PLUGIN_PREFIX, TVMenu, '')
    
    for k in range(24):
      dir.Append(DirectoryItem(nextTime, timeToDisplay(nextTime), thumb=R('blank-black.gif')))
      nextTime = nextTime + 1800
    dir.Append(Function(DirectoryItem(daysMenu, title=L('Another day'), thumb=R('blank-black.gif'))))
    dir.Append(Function(SearchDirectoryItem(searchMenu, title=l('Search'), prompt=L('Enter show name'))))
    
  dir.Append(Function(DirectoryItem(settingsMenu, title=L('Settings'), thumb=R('icon-settings.png'))))
  return dir

####################################################################################################  
  
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
  if getPref('timeFormat') == '12':
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
  
def meridianRangeTo24hour(s):
  (start, stop) = s.split('-')
  (stopTime, meridian) = re.match(r'(\d+:\d+)(\w\w)', stop).groups()
  if meridian == 'pm':
    baseHour = 12
  else:
    baseHour = 0
    
  (startHour, startMinute) = start.split(':')
  (stopHour, stopMinute) = stopTime.split(':')
  
  startHour = int(startHour) + baseHour
  stopHour = int(stopHour) + baseHour
  # 11:30-1:30AM -> 11:30-01:30 -> 23:30-01:30
  # 11:30-1:30PM -> 23:30-13:30 -> 11:30-13:30
  if startHour > stopHour: startHour = (startHour - 12) % 24
  
  start24 = str(startHour).zfill(2) + ':' + startMinute
  stop24 = str(stopHour).zfill(2) + ':' + stopMinute
  
  return start24 + '-' + stop24

####################################################################################################

def searchMenu(sender, query):
  dir = MediaContainer()
  Plugin.AddPathRequestHandler(SEARCH_PREFIX, showMenu, '', '', '')
  
  shows = GetXML(SEARCH_INDEX + String.Quote(query, True), True).xpath('//li[@class="zc-sr-l"]')
  if len(shows) == 0:
    # Here there was only one result
    shows = GetXML(SEARCH_INDEX + String.Quote(query, True), True).xpath('//table[@class="zc-episode"]')
    if len(shows) == 0:
      return movieMenu(SEARCH_INDEX + String.Quote(query, True))
    return grabShows(shows)
    
  # here there were multiple results
  for show in shows:
    name = show.xpath('child::a')[0].text
    description = show.xpath('child::span')[0].text
    link = show.xpath('child::a')[0].get('href')
    dir.Append(DirectoryItem(SEARCH_PREFIX + '/' + String.Encode(link) , title=name + ' ' + description))
  return dir

def showMenu(pathNouns, path):
  shows = GetXML(SHOW_INDEX + String.Decode(pathNouns[0]), True).xpath('//table[@class="zc-episode"]')
  if len(shows) == 0:
    return movieMenu(SHOW_INDEX + String.Decode(pathNouns[0]))
  return grabShows(shows)
  

def grabShows(shows):
  dir = MediaContainer()
  dir.viewGroup = 'Details'
  channels = getPref('channels')
  for show in shows:
    name = show.xpath('descendant::span[@class="zc-program-episode"]')[0]
    try:
      name = name.xpath('child::a')[0].text
    except:
      name = name.text.strip()
    description = show.xpath('descendant::span[@class="zc-program-description"]')[0].text + '\n'
    times = show.xpath('descendant::table[@class="zc-episode-times"]')[0].xpath('descendant::tr')
    for aTime in times:
      channel = aTime.xpath('child::td[@class="zc-channel"]')[0]
      if channel.text != None:
        channel =  channel.text
      else:
        channel = channel.xpath('child::span')[0].text
      #Log(channel)
      if channels[int(channel)]['enabled']:
        description = description + '\n' + aTime.xpath('child::td[@class="zc-sche-date"]')[0].text 
        
        timeRange = aTime.xpath('child::td[@class="zc-sche-time"]')[0].text
        if getPref('timeFormat') == '24':
          timeRange = meridianRangeTo24hour(timeRange)
        description = description + ' ' + timeRange
        description = description + ' ' + channel
        channelName = aTime.xpath('child::td[@class="zc-callsign"]')[0]
        try:
          description = description + ' ' + channelName.text
        except:
          description = description + ' ' + channelName.xpath('child::span')[0].text
    dir.Append(Function(DirectoryItem(noMenu, title=name, summary=description)))
  return dir
  
def movieMenu(url):
  dir = MediaContainer()
  dir.viewGroup = 'Details'
  page = GetXML(url, True)
  name = page.xpath('//h1[@id="zc-program-title"]')[0].text
  description = page.xpath('//p[@id="zc-program-description"]')[0].text + '\n\n'
  channels = getPref('channels')
  for aTime in page.xpath('//div[@id="zc-sc-ep-list"]')[0].xpath('child::ol[starts-with(@class,"zc-sc-ep-list-r")]'):
    channel = aTime.xpath('descendant::li[@class="zc-sc-ep-list-l zc-sc-ep-list-chn"]')[0].text
    if channels[int(channel)]['enabled']:
      description = description + ' ' + aTime.xpath('descendant::li[@class="zc-sc-ep-list-l zc-sc-ep-list-wd"]')[0].text
      description = description + ' ' + aTime.xpath('descendant::li[@class="zc-sc-ep-list-l zc-sc-ep-list-md"]')[0].text
      
      timeRange = aTime.xpath('descendant::li[@class="zc-sc-ep-list-l zc-sc-ep-list-stet"]')[0].text
      if getPref('timeFormat') == '24':
        timeRange = meridianRangeTo24hour(timeRange)
      description = description + ' ' + timeRange
      
      description = description + ' ' + channel
      description = description + ' ' + aTime.xpath('descendant::li[@class="zc-sc-ep-list-l zc-sc-ep-list-call"]')[0].text + '\n'
  dir.Append(Function(DirectoryItem(noMenu, title=name, summary=description)))
  return dir
    
####################################################################################################

def settingsMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Settings')
  dir.nocache = 1
  dir.Append(Function(SearchDirectoryItem(setPostalCode, title=L('PostalCodeTitle'), prompt=L('PostalCodePrompt'))))
  if getPref('postalCode') != '':
    dir.Append(Function(PopupDirectoryItem(providerMenu, title=L('Provider'))))
  if getPref('provider') != '':  
    dir.Append(Function(PopupDirectoryItem(timeFormatMenu, title=L('Time Format'))))
    dir.Append(Function(PopupDirectoryItem(inProgressMenu, title=L('Shows in progress'))))
    #if len(hideChannelsMenu(0)) != 0:
    dir.Append(Function(DirectoryItem(hideChannelsMenu, title=L('Hide Channels'))))
    #if len(showChannelsMenu(0)) != 0:
    dir.Append(Function(DirectoryItem(showChannelsMenu, title=L('Show Channels'))))
    dir.Append(Function(DirectoryItem(AddFavouritesMenu, title=('Add Favourites'))))
    dir.Append(Function(PopupDirectoryItem(collapseShowsMenu, title=L('Duplicates'))))
    
    favourites = getPref('favourites')
    if len(favourites) != 0:
      dir.Append(Function(DirectoryItem(RemoveFavouritesMenu, title=L('Remove Favourites'))))
  return dir

####################################################################################################
  
def setPostalCode(sender, query):
  query = string.join(query.split(' '),'') # No spaces please
  setPref('postalCode', query)
  return
  
####################################################################################################

def providerMenu(sender):
  dir = MediaContainer()
  url = 'http://tvlistings.zap2it.com/tvlistings/ZBChooseProvider.do?zipcode=' + getPref('postalCode') + '&method=getProviders'
  providers = XML.ElementFromString(HTTP.Request(url=url, cacheTime=CACHE_TIME), True).xpath('//a[starts-with(@href, "ZCGrid.do?method=decideFwdForLineup")]')
  for provider in providers:
    dir.Append(Function(DirectoryItem(setProvider, title=provider.text)))
  return dir
  
def setProvider(sender):
  Log(sender.itemTitle)
  url = 'http://tvlistings.zap2it.com/tvlistings/ZBChooseProvider.do?zipcode=' + getPref('postalCode') + '&method=getProviders'

  setProviderURL = XML.ElementFromString(HTTP.Request(url=url, cacheTime=CACHE_TIME), True).xpath('//a[text() = "' + sender.itemTitle + '"]')[0].get('href')
  #Log(re.search(r'lineupId=(.*)', setProviderURL).group(1))
  #Log(type(re.search(r'lineupId=(.*)', setProviderURL).group(1)))
  setPref('provider', re.search(r'lineupId=(.*)', setProviderURL).group(1))
  
  UpdateCache()
  return

####################################################################################################

def timeFormatMenu(sender):
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(setTimeFormat, title='12' + L('hour'))))
  dir.Append(Function(DirectoryItem(setTimeFormat, title='24' + L('hour'))))
  return dir

def setTimeFormat(sender):
  timeFormat = re.match(r'(\d\d).*', sender.itemTitle).group(1)
  setPref('timeFormat', timeFormat)
  return
  
####################################################################################################

def inProgressMenu(sender):
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(setInProgress, title=L('Show'))))
  dir.Append(Function(DirectoryItem(setInProgress, title=L('Hide'))))
  return dir

def setInProgress(sender):
  if sender.itemTitle == L('Show'):
    setPref('inProgress', True)
  else:
    setPref('inProgress', False)
  return
  
####################################################################################################

def collapseShowsMenu(sender):
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(setCollapse, title=L('Show'))))
  dir.Append(Function(DirectoryItem(setCollapse, title=L('Hide'))))
  return dir
  
def setCollapse(sender):
  if sender.itemTitle == L('Show'):
    v = False
  else:
    v = True
  setPref('collapseShows', v)
  
  return

####################################################################################################

def hideChannelsMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Hide Channels')
  dir.nocache = 1
  if sender == 0: dir.replaceParent = 1
  channels = getPref('channels')
  channelList = channels.keys()
  channelList.sort()
  for channel in channelList:
    if channels[channel]['enabled']:
      dir.Append(Function(DirectoryItem(hideChannel, title=str(channel) + ' ' + channels[channel]['name'])))
  return dir
  
def hideChannel(sender):
  (num, name) = sender.itemTitle.split(' ')
  channels = getPref('channels')
  channels[int(num)]['enabled'] = False
  setPref('channels', channels)
  return hideChannelsMenu(0)

####################################################################################################

def showChannelsMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Show Channels')
  dir.nocache = 1
  channels = getPref('channels')
  channelList = channels.keys()
  channelList.sort()
  for channel in channelList:
    if not channels[channel]['enabled']:
      dir.Append(Function(DirectoryItem(showChannel, title=str(channel) + ' ' + channels[channel]['name'])))
  return dir
  
def showChannel(sender):
  (num, name) = sender.itemTitle.split(' ')
  channels = getPref('channels')
  channels[int(num)]['enabled'] = True
  setPref('channels', channels)
  return

####################################################################################################

def AddFavouritesMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Add Favourites')
  dir.nocache = 1
  favourites = getPref('favourites')  
  try:
    if len(AddFavouritesMenu.allShows) != 0:
      for show in AddFavouritesMenu.allShows:
        if not show in favourites:
          dir.Append(Function(DirectoryItem(addFavourite, title=show)))
      return dir  
  except AttributeError:
    AddFavouritesMenu.allShows = list()
    slots = Dict.Get('shows')
    #showNames = list()
    
    for slot in slots.itervalues():
      for listing in slot:
        name = listing['title']
        if not name in AddFavouritesMenu.allShows and not name in favourites:
          AddFavouritesMenu.allShows.append(name)
    AddFavouritesMenu.allShows.sort()
    for showName in AddFavouritesMenu.allShows:
      dir.Append(Function(DirectoryItem(addFavourite, title=showName)))
    return dir
  
def addFavourite(sender):
  favourites = getPref('favourites')
  favourites.append(sender.itemTitle)
  setPref('favourites', favourites)
  return

####################################################################################################
  
def RemoveFavouritesMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Remove Favourites')
  dir.nocache = 1
  favourites = getPref('favourites')
  favourites.sort()
  for favourite in favourites:
    dir.Append(Function(DirectoryItem(removeFavourite, title=favourite)))
  return dir

def removeFavourite(sender):
  favourites = getPref('favourites')
  favourites.remove(sender.itemTitle)
  setPref('favourites', favourites)
  return
  
####################################################################################################

def grabListings(t, shows):
  url = PROVIDER_INDEX + '&zipcode=' + getPref('postalCode') + '&lineupId=' + getPref('provider') + '&fromTimeInMillis=' + str(t) + '000'
  for td in GetXML(url, True).xpath('//td[starts-with(@class,"zc-pg")]'):
    try: showName = td.xpath('child::a')[0].text.encode('ascii','ignore')
    except: showName = ''
    try: description = td.xpath('child::p')[0].text.encode('ascii','ignore')
    except: description = ''
    
    if (showName != '' or description != ''):
      try:
        channel = td.xpath('parent::*')[0].xpath('child::td[@class="zc-st"]')[0]
        channelNum = channel.xpath('descendant::span[@class="zc-st-n"]')[0].text
        channelName = channel.xpath('descendant::span[@class="zc-st-c"]')[0].text
        isValidChannel = True
      except:
        Log('Get channel failed:' + showName + ' ' + description)
        isValidChannel = False
        
      if isValidChannel:
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
        duration = int(re.search(r'(\d+)\)', td.get('onclick')).group(1)) * 60 # minutes->seconds
        endTime = startTime + duration
        endSlot = endTime - (endTime % 1800)
        
        if not startSlot in shows: shows[startSlot] = list()
        shows[startSlot].append(dict(title=showName, channelNum=channelNum, channelName=channelName, start=startTime, end=endTime, summary=description, inProgress=False))
        for slot in range(startSlot + 1800, endSlot, 1800):
          if not slot in shows: shows[slot] = list()
          shows[slot].append(dict(title=showName, channelNum=channelNum, channelName=channelName, start=startTime, end=endTime, summary=description, inProgress=True))

####################################################################################################

def TVMenu(pathNouns, path):
  dir = MediaContainer()
  dir.viewGroup = 'Details'
  menuTime = int(pathNouns[0])
  dir.title2 = timeToDisplay(menuTime)
  dir.nocache = 1
  
  listings = Dict.Get('shows')
  if not menuTime in listings:
    grabListings(menuTime, listings)
  listings = listings[menuTime]
  
  collapse = getPref('collapseShows')
  if collapse:
    keyDict = dict()
  
  displayInProgress = getPref('inProgress')
  channels = getPref('channels')
  favourites = getPref('favourites')
  hits = list()
  misses = list()
  for listing in listings:
    timeString = timeToDisplay(listing['start']) + ' - ' + timeToDisplay(listing['end'])
    if (displayInProgress or not listing['inProgress']) and channels[int(listing['channelNum'])]['enabled']:
      # check if we should collapse it
      listingKey = (frozenset([listing['title'], listing['summary'], listing['start'], listing['end']]))
      if not collapse or listingKey not in keyDict:
        keyDict[listingKey] = '' 
        newItem = Function(DirectoryItem(noMenu, title=listing['title'], subtitle=listing['channelNum'] + ' ' + listing['channelName'] + ' ' + timeString, summary=listing['summary']))
        if listing['title'] in favourites:
          hits.append(newItem)
        else:
          misses.append(newItem)
        
  for hit in hits:
    dir.Append(hit)
  for miss in misses:
    dir.Append(miss)

  return dir
  
####################################################################################################

def daysMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Days')
  Plugin.AddPathRequestHandler(DAY_PREFIX, dayMenu, '', '', '')

  (year, month, day) = datetime.datetime.today().timetuple()[0:3]
  dayOfWeek = calendar.weekday(year, month, day)
  
  midnight = datetime.datetime.fromordinal(datetime.datetime.now().toordinal())
  midnight = calendar.timegm(midnight.timetuple())
  if time.daylight != 0:
    midnight = midnight + time.altzone 
  else:
    midnight = midnight + time.timezone


  for dayCount in range(7):
    dir.Append(DirectoryItem(DAY_PREFIX + '/' + str(midnight), title=calendar.day_name[dayOfWeek]))
    dayOfWeek = (dayOfWeek + 1) % 7
    midnight = midnight + DAY

  return dir

def dayMenu(pathNouns, path):
  dir = MediaContainer()  
  Plugin.AddPathRequestHandler(PLUGIN_PREFIX, TVMenu, '', '', '')
    
  nextTime = int(pathNouns[0])
  for k in range(48):
    dir.Append(DirectoryItem(PLUGIN_PREFIX + '/' + str(nextTime), timeToDisplay(nextTime), '',''))
    nextTime = nextTime + 1800
  return dir

####################################################################################################

def noMenu(sender):
  pass

####################################################################################################

def GetXML(theUrl, use_html_parser=False):
  return XML.ElementFromString(HTTP.Request(url=theUrl, cacheTime=CACHE_TIME), use_html_parser)

####################################################################################################

def setPref(id, value):
  Prefs.Set(id, pickle.dumps(value))

def getPref(id):
  return pickle.loads(Prefs.Get(id))
  
def addPref(id, kind, default, name):
  Prefs.Add(id, kind, pickle.dumps(default), name)
  
####################################################################################################
