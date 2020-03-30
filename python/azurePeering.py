def azure_peering(sub1, rg1, vnet1, sub2, rg2, vnet2):

    CREDENTIALS = ServicePrincipalCredentials(
        client_id = os.environ['ARM_CLIENT_ID'],
        secret = os.environ['ARM_CLIENT_SECRET'],
        tenant = os.environ['ARM_TENANT_ID']
    )
    network_client_1 = NetworkManagementClient(CREDENTIALS,sub1)
    network_client_2 = NetworkManagementClient(CREDENTIALS,sub2)

    vnet1_obj = network_client_1.virtual_networks.get(rg1, vnet1)
    vnet2_obj = network_client_2.virtual_networks.get(rg2, vnet2)

    try:
        async_vnet_peering = network_client_1.virtual_network_peerings.create_or_update(
            rg1,
            vnet1,
            "hubpeering",
            {
                "remote_virtual_network": {
                    "id": vnet2_obj.id
                },
                'allow_virtual_network_access': True,
                'allow_forwarded_traffic': True,
                'remote_address_space': {
                    'address_prefixes': vnet2_obj.address_space.address_prefixes
                }
            }
        ) 
        while not async_vnet_peering.done():
            time.sleep(2)
            print(f'Peering: {async_vnet_peering.status()}')
        print(' ********** peering completed **********')
    except CloudError as ex:
        print(str(ex))
