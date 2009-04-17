from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *


import re, string, datetime, time

PLUGIN_PREFIX = "/video/zap2it"
PROVIDER_INDEX = "http://tvlistings.zap2it.com/tvlistings/ZCGrid.do?aid=zap2it&isDescriptionOn=true"
CACHE_TIME = 1800

####################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L("Zap2it"))
  
  Plugin.AddViewGroup("Details", viewMode="InfoList", mediaType="items")
  Plugin.AddViewGroup("PlainList", viewMode="List", mediaType="items")
  Plugin.AddViewGroup("EpisodeList", viewMode="Episodes", mediaType="items")
  
  MediaContainer.title1 = L("Zap2it")
  MediaContainer.viewGroup = "EpisodeList"
  MediaContainer.art = R("art-default.jpg")
  
  HTTP.SetCacheTime(CACHE_TIME)
  
####################################################################################################

def CreateDict():
  Dict.Set('channels', list())
  Dict.Set('postalCode', '')
  Dict.Set('provider', '')

####################################################################################################

def UpdateCache():
  # Get TV Page
  if Dict.Get('postalCode') == '' or Dict.Get('provider') == '':
    return
  now = datetime.datetime.now()
  nextTime = [now.hour, 0]
  if now.minute < 30:
    nextTime[1] = 0
  else:
    nextTime[1] = 30
  sender = ItemInfoRecord()
  sender.itemTitle = str(nextTime[0]) + ':' + str(nextTime[1])
  TVMenu(sender=sender)

####################################################################################################

# TODO: Allow access to later times &fromTimeInMillis=
# TODO: Decrease number of cached pages to 1 per 3 hours
# TODO: Option for 12-hour time format

def MainMenu():
  dir = MediaContainer()
  now = datetime.datetime.now()
  nextTime = [now.hour, 0]
  if now.minute < 30:
    nextTime[1] = 0
  else:
    nextTime[1] = 30  
  if Dict.Get('postalCode') != '' and Dict.Get('provider') != '':
    for k in range(6):
      dir.Append(Function(DirectoryItem(TVMenu, title=str(nextTime[0]) + ':' + str(nextTime[1]).zfill(2) )))
      nextTime = inc30(nextTime[0], nextTime[1])
  
  dir.Append(Function(DirectoryItem(settingsMenu, title=L('Settings'))))
  return dir


def inc30(hour, minute):
  if minute == 0:
    minute = 30
  else:
    hour = hour + 1
    minute = 0
    if hour > 23: hour = hour - 24
    
  return (hour, minute)
  
  
def settingsMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Settings')
  dir.Append(Function(SearchDirectoryItem(setPostalCode, title='ZIP or Postal Code', prompt='Enter your ZIP or Postal Code')))
  if Dict.Get('postalCode') != '':
    dir.Append(Function(PopupDirectoryItem(providerMenu, title='Provider')))
  
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


def TVMenu(sender):
  dir = MediaContainer()
  dir.title2 = sender.itemTitle
  dir.viewGroup = "Details"
  
  url = PROVIDER_INDEX 
  postalCode = Dict.Get('postalCode')
  if postalCode != '': url = url + '&zipcode=' + postalCode

  provider = Dict.Get('provider')
  if provider != '': url = url + '&lineupId=' + provider

  if time.daylight != 0:
    timeZone = time.altzone 
  else:
    timeZone = time.timezone

  (hour, minute) = sender.itemTitle.split(':')
  menuTime = int(minute) * 60 + int(hour) * 3600
  Log(str(menuTime //1800))

  for td in GetXML(url, True).xpath('//td[starts-with(@class,"zc-pg")]'):
    try: showName = td.xpath('child::a')[0].text.encode('ascii','ignore')
    except: showName = ''
    try: description = td.xpath('child::p')[0].text.encode('ascii','ignore')
    except: description = ''
    
    startTime = int(re.search(r'(?:([^,]+),)*', td.get('onclick')).group(1)) // 1000
    startTime = ((startTime % 86400) - timeZone) % 86400
    
    if (showName != '' or description != '') and startTime // 1800 == menuTime // 1800:  
      duration = int(re.search(r'(\d+)', td.get('style')).group(0)) * 15 # seconds
      
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
      
      endTime = (startTime + duration) % 86400
      timeString = str(startTime // 3600) + ":" + str(startTime % 3600 // 60).zfill(2) + ' - ' + str(endTime // 3600) + ":" + str(endTime % 3600 // 60).zfill(2)
      
      dir.Append(Function(DirectoryItem(noMenu, title=showName, subtitle=channelNum + ' ' + channelName + ' ' + timeString, summary=description)))
      #Log('name: ' + showName + ' description: ' + description + ' start: ' + str(startTime)) 

  return dir
  
  
def noMenu(sender):
  pass

####################################################################################################
def GetXML(theUrl, use_html_parser=False):
  return XML.ElementFromString(HTTP.Request(url=theUrl, cacheTime=CACHE_TIME), use_html_parser)


####################################################################################################
