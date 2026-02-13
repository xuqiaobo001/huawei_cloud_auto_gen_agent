# 所有华为云服务的完整API操作列表

SERVICES_DATA = {
    "ecs": {
        "description": "弹性云服务器",
        "module": "huaweicloudsdkecs",
        "client": "EcsClient",
        "operations": [
            "create_servers", "list_servers", "get_server", "delete_servers", "update_server",
            "start_server", "stop_server", "reboot_server", "batch_start_servers", "batch_stop_servers",
            "batch_reboot_servers", "batch_create_server_tags", "batch_delete_server_tags",
            "attach_server_volume", "detach_server_volume", "list_server_volumes",
            "batch_attach_sharable_volumes", "batch_detach_sharable_volumes",
            "show_server_remote_console", "batch_create_servers_tags", "batch_show_servers",
            "list_server_interfaces", "batch_add_server_nics", "batch_delete_server_nics",
            "add_server_group_member", "batch_add_server_group_member", "batch_delete_server_group_member",
            "create_server_group", "delete_server_group", "list_server_groups", "show_server_group",
            "change_server_os", "update_server_metadata", "show_server_password", "reset_server_password",
            "config_ipv6_bandwidth", "show_ipv6_bandwidth", "associate_server_virtual_ip",
            "disassociate_server_virtual_ip", "nova_associate_server_virtual_ip", "nova_disassociate_server_virtual_ip",
            "nova_list_server_volumes", "nova_attach_server_volume", "nova_detach_server_volume",
            "nova_get_server_volumes", "list_versions", "show_version",
            "create_server_console_login", "show_server_console_login_info", "delete_server_console_login_info",
            "batch_update_server_tags", "batch_delete_server_tags", "list_project_server_tags",
            "list_server_tags", "tag_servers", "untag_servers", "show_server_tags",
            "create_server_remote_console", "attach_and_import_volume", "create_post_paid_servers",
            "resize_server", "confirm_resize_server", "revert_resize_server", "cold_migrate_server",
            "resize_prepaid_server", "register_server_auto_recovery", "unregister_server_auto_recovery",
            "show_server_auto_recovery", "register_server_monitor", "unregiter_server_monitor"
        ]
    }
}
