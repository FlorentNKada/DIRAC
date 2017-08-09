########################################################################
# $HeadURL $
# File: ForwardDISET.py
# Author: Krzysztof.Ciba@NOSPAMgmail.com
# Date: 2013/03/22 12:40:06
########################################################################
""" :mod: ForwardDISET

    ==================

    .. module: ForwardDISET

    :synopsis: DISET forwarding operation handler

    .. moduleauthor:: Krzysztof.Ciba@NOSPAMgmail.com

    DISET forwarding operation handler
"""

__RCSID__ = "$Id $"

# #
# @file ForwardDISET.py
# @author Krzysztof.Ciba@NOSPAMgmail.com
# @date 2013/03/22 12:40:22
# @brief Definition of ForwardDISET class.

# # imports
from DIRAC import S_OK, S_ERROR, gConfig
from DIRAC.RequestManagementSystem.private.OperationHandlerBase import OperationHandlerBase
from DIRAC.Core.DISET.RPCClient import executeRPCStub
from DIRAC.Core.Utilities import DEncode
from DIRAC.ConfigurationSystem.Client.ConfigurationData import gConfigurationData

########################################################################
class ForwardDISET( OperationHandlerBase ):
  """
  .. class:: ForwardDISET

  functor forwarding DISET operations
  """
  def __init__( self, operation = None, csPath = None ):
    """ c'tor

    :param Operation operation: an Operation instance
    :param str csPath: CS path for this handler
    """
    # # call base class c'tor
    OperationHandlerBase.__init__( self, operation, csPath )

  def __call__( self ):
    """ execute RPC stub """
    # # decode arguments
    try:
      decode, length = DEncode.decode( self.operation.Arguments )
      self.log.debug( "decoded val=%s" %  decode )
    except ValueError, error:
      self.log.exception( error )
      self.operation.Error = str( error )
      self.operation.Status = "Failed"
      return S_ERROR( str( error ) )

    # ForwardDiset is supposed to be used with a host certificate
    useServerCertificate = gConfig.useServerCertificate()
    gConfigurationData.setOptionInCFG( '/DIRAC/Security/UseServerCertificate', 'true' )
    forward = executeRPCStub( decode )
    if not useServerCertificate:
      gConfigurationData.setOptionInCFG( '/DIRAC/Security/UseServerCertificate', 'false' )

    if not forward["OK"]:
      self.log.error( "unable to execute operation", "'%s' : %s" % ( self.operation.Type, forward["Message"] ) )
      self.operation.Error = forward["Message"]
      return forward
    self.log.info( "DISET forwarding done" )
    self.operation.Status = "Done"
    return S_OK()
