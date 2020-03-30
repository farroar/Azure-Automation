#!/usr/bin/python3 
'''
# This script spins up an Azure firewall instance and returns
# the firewall object. This object can be used to inform other
# scripts. For example, if you wanted to update routing to reflect
# the private IP of the firewall, you could pull that from the
# object
#
# input into this function is class called 'vnet'. This class
# contains all of the variables and values to inform this script
# Substitute where necessary.
'''


import os
import random
import string
import time

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from msrestazure.azure_exceptions import CloudError

def azure_firewall_deploy(vnet, network_client):
    fw_name = vnet.orgName+'-'+vnet.name+'-azfw'
    pip_name = vnet.name+'-pip'
    resource_group = vnet.resourceGroup
    location = vnet.location
    vnet_name = vnet.orgName+'-'+vnet.name+'-vnet'

    #already exists?
    try:
        check = network_client.public_ip_addresses.get(
            resource_group,
            pip_name
        )
        check_value = True
        print(f'Public IP {pip_name} already exists')
    except:
        check_value = False

    #create public IP
    if not check_value:
        pip = network_client.public_ip_addresses.create_or_update(
            resource_group,
            pip_name,
            {
                'location': location,
                'sku': {
                    'name': 'standard'
                },
                'public_ip_allocation_method': 'static',        
            }
        )
        while not pip.done():
            pip_status = pip.status()
            print(pip_status)
            time.sleep(1.5)
    
    pip_info = network_client.public_ip_addresses.get(
        resource_group,
        pip_name
    )
    subnet_info = network_client.subnets.get(
        resource_group,
        vnet_name,
        'AzureFirewallSubnet'
    )

    #check if firewall already exists
    try:
        check_value = network_client.azure_firewalls.get(
            resource_group,
            fw_name
        )
        checK_value = True
        print(f'Firewall {fw_name} already exists')
    except:
        check_value = False

    #deploy firewall if not exist
    if not check_value:
        try:
            azfw = network_client.azure_firewalls.create_or_update(
                resource_group,
                fw_name,
                {
                    'location': 'eastus',
                    'ip_configurations': [{
                        'name': 'ipconfig',
                        'subnet': {
                            'id': subnet_info.id
                        },
                        'public_ip_address': {
                            'id': pip_info.id
                        }
                    }]
                }
            )
        except CloudError as ex:
            print(str(ex))
        
        while not azfw.done():
            fw_status = azfw.status()
            print(f' Azure firewall deployment - {fw_status}')
            time.sleep(1.5)

    azfw_info = network_client.azure_firewalls.get(
        resource_group,
        fw_name
    )

    #return firewall object
    return azfw_info
