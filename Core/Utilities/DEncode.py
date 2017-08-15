# $HeadURL$

###############################################################################
#                         DEncode_json_only.py                                #
###############################################################################
__RCSID__ = "$Id$"

import json
import types
import datetime
import string

_dateTimeObject = datetime.datetime.utcnow()
_dateTimeType = type( _dateTimeObject )
_dateType = type( _dateTimeObject.date() )
_timeType = type( _dateTimeObject.time() )

################################################################################
#                  New code for JSON (un)marshalling                           #
################################################################################
def hintParticularTypes( item ):
  """This function detects tuples and longs and replaces them with dictionaries.
  This allows us to prserve these data types. By default, 'json.dumps()' encodes
  tuples into arrays, (like python lists) and longs into int numbers
  (like python ints). By using directly 'json.loads()', without
  'DEncode.hintParticularTypes()', arrays are decoded into lists (so we
  lose our tuples) and int numbers into ints (then we also lose long ints)."""

  if isinstance( item, tuple ):
    L = []
    for i in item:
      L.append( hintParticularTypes( i ) )
    newTuple = tuple( L )
    return {'__tuple__': True, 'items': newTuple}
  elif isinstance( item, long ):
    return {'__long__': True, 'value': item}
  elif isinstance( item, list ):
    return [hintParticularTypes(e) for e in item]
  elif isinstance( item, dict ):
    newDict = {}
    for key in item:
      newDict[key] = hintParticularTypes( item[key] )
    return newDict
  elif isinstance( item, _dateTimeType ):
    dateTimeTuple = ( item.year, item.month, item.day, item.hour,
                      item.minute, item.second,
                      item.microsecond, item.tzinfo )
    return {'__dateTime__':True, 'items':dateTimeTuple}
  elif isinstance(item, _dateType):
    dateTuple = ( item.year, item.month, item. day )
    return {"__date__":True, 'items':dateTuple}
  elif isinstance(item, _timeType):
    timeTuple = ( item.hour, item.minute, item.second, item.microsecond, item.tzinfo )
    return {"__time__":True, 'items':timeTuple}
  else:
    return item

def DetectHintedParticularTypes( object ):
  """This function detecs dictionaries encoding tuples and longs and replaces
  them with the correct data structures. """
  newTuple = tuple()
  if isinstance(object, list):
    return [DetectHintedParticularTypes(e) for e in object]
  elif isinstance( object, dict ):
    if '__tuple__' in object:
      newTuple = DetectHintedParticularTypes( object['items'] )
      return tuple(newTuple)
    elif '__long__' in object:
      return long( object['value'] )
    elif '__dateTime__' in object:
      L = list()
      for i in object['items']:
        L.append(i)
      newTuple = tuple(L)
      return datetime.datetime(*newTuple)
    elif '__date__' in object:
      L = list()
      for i in object['items']:
        L.append(i)
      newTuple = tuple(L)
      return datetime.date(*newTuple)
    elif '__time__' in object:
      L = list()
      for i in object['items']:
        L.append(i)
      newTuple = tuple(L)
      return datetime.time(*newTuple)
    else:
      newDict = {}
      for key in object:
        newDict[key] = DetectHintedParticularTypes( object[key] )
      return newDict
  elif isinstance(object, tuple):
    L = list()
    for i in object:
      L.append( DetectHintedParticularTypes( i ) )
    newTuple = tuple( L )
    return newTuple
  else:
    return object

class newEncoder(json.JSONEncoder):
  def encode( self, object ):
    return super( newEncoder, self ).encode( hintParticularTypes( object ) )

#################################################################################
#################################################################################
def encode( uObject ):
  """This function turns the uObject data into serialized data.
  the serialized data is written in JSON format."""

  try:                                         
    coding = newEncoder()                                              
    jsonString = coding.encode( uObject )                              
    return jsonString 
  except Exception:                                                      
     raise                                                              

def decode( data ):
  """This function turns a serialized string into a data structure."""

  if not data:
    return data
  try:
    return json.loads( data, object_hook =  DetectHintedParticularTypes )
  except Exception:
    raise
