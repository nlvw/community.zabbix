#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2013-2014, Epic Games, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = r'''
---
module: zabbix_screen
short_description: Create/update/delete Zabbix screens
description:
    - This module allows you to create, modify and delete Zabbix screens and associated graph data.
author:
    - "Cove (@cove)"
    - "Tony Minfei Ding (!UNKNOWN)"
    - "Harrison Gu (@harrisongu)"
requirements:
    - "python >= 2.6"
    - "Zabbix <= 5.2"
options:
    screens:
        description:
            - List of screens to be created/updated/deleted (see example).
        type: list
        elements: dict
        required: true
        suboptions:
            screen_name:
                description:
                    - Screen name will be used.
                    - If a screen has already been added, the screen name won't be updated.
                type: str
                required: true
            host_group:
                description:
                    - Host group(s) will be used for searching hosts.
                    - Required if I(state=present).
                type: list
                elements: str
                aliases: [ 'host_groups' ]
            state:
                description:
                    - I(present) - Create a screen if it doesn't exist. If the screen already exists, the screen will be updated as needed.
                    - I(absent) - If a screen exists, the screen will be deleted.
                type: str
                default: present
                choices:
                    - absent
                    - present
            graph_names:
                description:
                    - Graph names will be added to a screen. Case insensitive.
                    - Required if I(state=present).
                type: list
                elements: str
            graph_width:
                description:
                    - Graph width will be set in graph settings.
                type: int
            graph_height:
                description:
                    - Graph height will be set in graph settings.
                type: int
            graphs_in_row:
                description:
                    - Limit columns of a screen and make multiple rows.
                type: int
                default: 3
            sort:
                description:
                    - Sort hosts alphabetically.
                    - If there are numbers in hostnames, leading zero should be used.
                type: bool
                default: no

extends_documentation_fragment:
- community.zabbix.zabbix


notes:
    - Too many concurrent updates to the same screen may cause Zabbix to return errors, see examples for a workaround if needed.
    - Screens where removed from Zabbix with Version 5.4
'''

EXAMPLES = r'''
# Set following variables for Zabbix Server host in play or inventory
- name: Set connection specific variables
  set_fact:
    ansible_network_os: community.zabbix.zabbix
    ansible_connection: httpapi
    ansible_httpapi_port: 80
    ansible_httpapi_use_ssl: false
    ansible_httpapi_validate_certs: false
    ansible_zabbix_url_path: 'zabbixeu'  # If Zabbix WebUI runs on non-default (zabbix) path ,e.g. http://<FQDN>/zabbixeu

# If you want to use Username and Password to be authenticated by Zabbix Server
- name: Set credentials to access Zabbix Server API
  set_fact:
    ansible_user: Admin
    ansible_httpapi_pass: zabbix

# If you want to use API token to be authenticated by Zabbix Server
# https://www.zabbix.com/documentation/current/en/manual/web_interface/frontend_sections/administration/general#api-tokens
- name: Set API token
  set_fact:
    ansible_zabbix_auth_key: 8ec0d52432c15c91fcafe9888500cf9a607f44091ab554dbee860f6b44fac895

# Screens where removed from Zabbix with Version 5.4

# Create/update a screen.
- name: Create a new screen or update an existing screen's items 5 in a row
  community.zabbix.zabbix_screen:
    screens:
      - screen_name: ExampleScreen1
        host_group: Example group1
        state: present
        graph_names:
          - Example graph1
          - Example graph2
        graph_width: 200
        graph_height: 100
        graphs_in_row: 5

# Create/update multi-screen
- name: Create two of new screens or update the existing screens' items
  community.zabbix.zabbix_screen:
    screens:
      - screen_name: ExampleScreen1
        host_group: Example group1
        state: present
        graph_names:
          - Example graph1
          - Example graph2
        graph_width: 200
        graph_height: 100
      - screen_name: ExampleScreen2
        host_group: Example group2
        state: present
        graph_names:
          - Example graph1
          - Example graph2
        graph_width: 200
        graph_height: 100

# Limit the Zabbix screen creations to one host since Zabbix can return an error when doing concurrent updates
- name: Create a new screen or update an existing screen's items
  community.zabbix.zabbix_screen:
    state: present
    screens:
      - screen_name: ExampleScreen
        host_group: Example group
        state: present
        graph_names:
          - Example graph1
          - Example graph2
        graph_width: 200
        graph_height: 100
  when: inventory_hostname==groups['group_name'][0]

# Create/update using multiple hosts_groups. Hosts NOT present in all listed host_groups will be skipped.
- name: Create new screen or update the existing screen's items for hosts in both given groups
  community.zabbix.zabbix_screen:
    screens:
      - screen_name: ExampleScreen1
        host_group:
          - Example group1
          - Example group2
        state: present
        graph_names:
          - Example graph1
          - Example graph2
        graph_width: 200
        graph_height: 100
'''


from ansible.module_utils.basic import AnsibleModule

from ansible_collections.community.zabbix.plugins.module_utils.base import ZabbixBase
from ansible_collections.community.zabbix.plugins.module_utils.wrappers import ScreenItem
from ansible_collections.community.zabbix.plugins.module_utils.version import LooseVersion

import ansible_collections.community.zabbix.plugins.module_utils.helpers as zabbix_utils


class Screen(ZabbixBase):
    # get list of group ids by list of group names
    def get_host_group_ids(self, group_names):
        if not group_names:
            self._module.fail_json(msg="group_name is required")
        hostGroup_list = self._zapi.hostgroup.get({'output': 'extend', 'filter': {'name': group_names}})
        if not hostGroup_list:
            self._module.fail_json(msg="Host group not found: {0}".format(group_names))
        else:
            hostGroup_ids = [g['groupid'] for g in hostGroup_list]
            return hostGroup_ids

    # get monitored host_ids by host_group_ids
    # (the hosts belonging to all given groups)
    def get_host_ids_by_group_ids(self, group_ids, sort):
        host_list = self._zapi.host.get({'output': 'extend', 'selectGroups': 'groupid', 'groupids': group_ids, 'monitored_hosts': 1})
        if not host_list:
            self._module.fail_json(msg="No hosts in the all group(s) with ids {0}".format(group_ids))
        else:
            if sort:
                host_list = sorted(host_list, key=lambda name: name['name'])
            host_ids = []
            for host in host_list:
                host_group_ids = [g['groupid'] for g in host['groups']]
                # Check if all search group ids are in hosts group ids
                if set(group_ids).issubset(host_group_ids):
                    host_id = host['hostid']
                    host_ids.append(host_id)
            return host_ids

    # get screen
    def get_screen_id(self, screen_name):
        if screen_name == "":
            self._module.fail_json(msg="screen_name is required")
        try:
            screen_id_list = self._zapi.screen.get({'output': 'extend', 'search': {"name": screen_name}})
            if len(screen_id_list) >= 1:
                screen_id = screen_id_list[0]['screenid']
                return screen_id
            return None
        except Exception as e:
            self._module.fail_json(msg="Failed to get screen %s from Zabbix: %s" % (screen_name, e))

    # create screen
    def create_screen(self, screen_name, h_size, v_size):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            screen = self._zapi.screen.create({'name': screen_name, 'hsize': h_size, 'vsize': v_size})
            return screen['screenids'][0]
        except Exception as e:
            self._module.fail_json(msg="Failed to create screen %s: %s" % (screen_name, e))

    # update screen
    def update_screen(self, screen_id, screen_name, h_size, v_size):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            self._zapi.screen.update({'screenid': screen_id, 'hsize': h_size, 'vsize': v_size})
        except Exception as e:
            self._module.fail_json(msg="Failed to update screen %s: %s" % (screen_name, e))

    # delete screen
    def delete_screen(self, screen_id, screen_name):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            self._zapi.screen.delete([screen_id])
        except Exception as e:
            self._module.fail_json(msg="Failed to delete screen %s: %s" % (screen_name, e))

    # get graph ids
    def get_graph_ids(self, hosts, graph_name_list):
        graph_id_lists = []
        vsize = 1
        for host in hosts:
            graph_id_list = self.get_graphs_by_host_id(graph_name_list, host)
            size = len(graph_id_list)
            if size > 0:
                graph_id_lists.extend(graph_id_list)
                if vsize < size:
                    vsize = size
        return graph_id_lists, vsize

    #  getGraphs
    def get_graphs_by_host_id(self, graph_name_list, host_id):
        graph_ids = []
        for graph_name in graph_name_list:
            graphs_list = self._zapi.graph.get({'output': 'extend', 'search': {'name': graph_name}, 'hostids': host_id})
            graph_id_list = []
            if len(graphs_list) > 0:
                for graph in graphs_list:
                    graph_id = graph['graphid']
                    graph_id_list.append(graph_id)
            if len(graph_id_list) > 0:
                graph_ids.extend(graph_id_list)
        return graph_ids

    # get screen items
    def get_screen_items(self, screen_id):
        screen_item_list = self._zapi.screenitem.get({'output': 'extend', 'screenids': screen_id})
        return screen_item_list

    # delete screen items
    def delete_screen_items(self, screen_id, screen_item_id_list):
        if len(screen_item_id_list) == 0:
            return True
        screen_item_list = self.get_screen_items(screen_id)
        if len(screen_item_list) > 0:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            ScreenItem.delete(self, screen_item_id_list)
            return True
        return False

    # get screen's hsize and vsize
    def get_hsize_vsize(self, hosts, v_size, graphs_in_row):
        h_size = len(hosts)
        # when there is only one host, put all graphs in a row
        if h_size == 1:
            if v_size <= graphs_in_row:
                h_size = v_size
            else:
                h_size = graphs_in_row
            v_size = (v_size - 1) // h_size + 1
        # when len(hosts) is more then graphs_in_row
        elif len(hosts) > graphs_in_row:
            h_size = graphs_in_row
            v_size = (len(hosts) // graphs_in_row + 1) * v_size

        return h_size, v_size

    # create screen_items
    def create_screen_items(self, screen_id, hosts, graph_name_list, width, height, h_size, graphs_in_row):
        if len(hosts) < 4:
            if width is None or width < 0:
                width = 500
        else:
            if width is None or width < 0:
                width = 200
        if height is None or height < 0:
            height = 100

        # when there're only one host, only one row is not good.
        if len(hosts) == 1:
            graph_id_list = self.get_graphs_by_host_id(graph_name_list, hosts[0])
            for i, graph_id in enumerate(graph_id_list):
                if graph_id is not None:
                    ScreenItem.create(self, ignoreExists=True, data={'screenid': screen_id, 'resourcetype': 0, 'resourceid': graph_id,
                                                                     'width': width, 'height': height,
                                                                     'x': i % h_size, 'y': i // h_size, 'colspan': 1, 'rowspan': 1,
                                                                     'elements': 0, 'valign': 0, 'halign': 0,
                                                                     'style': 0, 'dynamic': 0, 'sort_triggers': 0})
        else:
            for i, host in enumerate(hosts):
                graph_id_list = self.get_graphs_by_host_id(graph_name_list, host)
                for j, graph_id in enumerate(graph_id_list):
                    if graph_id is not None:
                        ScreenItem.create(self, ignoreExists=True, data={'screenid': screen_id, 'resourcetype': 0, 'resourceid': graph_id,
                                                                         'width': width, 'height': height,
                                                                         'x': i % graphs_in_row, 'y': len(graph_id_list) * (i // graphs_in_row) + j,
                                                                         'colspan': 1, 'rowspan': 1,
                                                                         'elements': 0, 'valign': 0, 'halign': 0,
                                                                         'style': 0, 'dynamic': 0, 'sort_triggers': 0})


def main():
    argument_spec = zabbix_utils.zabbix_common_argument_spec()
    argument_spec.update(dict(
        screens=dict(
            type='list',
            elements='dict',
            required=True,
            options=dict(
                screen_name=dict(type='str', required=True),
                host_group=dict(type='list', aliases=['host_groups'], elements='str'),
                state=dict(type='str', default='present', choices=['absent', 'present']),
                graph_names=dict(type='list', elements='str'),
                graph_width=dict(type='int', default=None),
                graph_height=dict(type='int', default=None),
                graphs_in_row=dict(type='int', default=3),
                sort=dict(default=False, type='bool'),
            ),
            required_if=[
                ['state', 'present', ['host_group']]
            ]
        )
    ))
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    zabbix_utils.require_creds_params(module)

    for p in ['server_url', 'login_user', 'login_password']:
        if p in module.params and module.params[p]:
            module.warn('Option "%s" is deprecated with the move to httpapi connection and will be removed in the next release' % p)

    screens = module.params['screens']

    screen = Screen(module)
    if LooseVersion(screen._zbx_api_version) >= LooseVersion('5.4'):
        module.fail_json(msg="Zabbix 5.4 removed the Screens feature see (%s)." % (
            "https://www.zabbix.com/documentation/current/en/manual/api/changes_5.2_-_5.4"
        ))

    created_screens = []
    changed_screens = []
    deleted_screens = []

    for zabbix_screen in screens:
        screen_name = zabbix_screen['screen_name']
        screen_id = screen.get_screen_id(screen_name)
        state = zabbix_screen['state']
        sort = zabbix_screen['sort']

        if state == "absent":
            if screen_id:
                screen_item_list = screen.get_screen_items(screen_id)
                screen_item_id_list = []
                for screen_item in screen_item_list:
                    screen_item_id = screen_item['screenitemid']
                    screen_item_id_list.append(screen_item_id)
                screen.delete_screen_items(screen_id, screen_item_id_list)
                screen.delete_screen(screen_id, screen_name)

                deleted_screens.append(screen_name)
        else:
            host_group = zabbix_screen['host_group']
            graph_names = zabbix_screen['graph_names']
            graphs_in_row = zabbix_screen['graphs_in_row']
            graph_width = zabbix_screen['graph_width']
            graph_height = zabbix_screen['graph_height']
            host_group_ids = screen.get_host_group_ids(host_group)
            hosts = screen.get_host_ids_by_group_ids(host_group_ids, sort)
            if not hosts:
                module.fail_json(msg="No hosts found belongin to all given groups: %s" % host_group)
            screen_item_id_list = []
            resource_id_list = []

            graph_ids, v_size = screen.get_graph_ids(hosts, graph_names)
            h_size, v_size = screen.get_hsize_vsize(hosts, v_size, graphs_in_row)

            if not screen_id:
                # create screen
                screen_id = screen.create_screen(screen_name, h_size, v_size)
                screen.create_screen_items(screen_id, hosts, graph_names, graph_width, graph_height, h_size, graphs_in_row)
                created_screens.append(screen_name)
            else:
                screen_item_list = screen.get_screen_items(screen_id)

                for screen_item in screen_item_list:
                    screen_item_id = screen_item['screenitemid']
                    resource_id = screen_item['resourceid']
                    screen_item_id_list.append(screen_item_id)
                    resource_id_list.append(resource_id)

                # when the screen items changed, then update
                if graph_ids != resource_id_list:
                    deleted = screen.delete_screen_items(screen_id, screen_item_id_list)
                    if deleted:
                        screen.update_screen(screen_id, screen_name, h_size, v_size)
                        screen.create_screen_items(screen_id, hosts, graph_names, graph_width, graph_height, h_size, graphs_in_row)
                        changed_screens.append(screen_name)

    if created_screens and changed_screens:
        module.exit_json(changed=True, result="Successfully created screen(s): %s, and updated screen(s): %s" % (",".join(created_screens),
                                                                                                                 ",".join(changed_screens)))
    elif created_screens:
        module.exit_json(changed=True, result="Successfully created screen(s): %s" % ",".join(created_screens))
    elif changed_screens:
        module.exit_json(changed=True, result="Successfully updated screen(s): %s" % ",".join(changed_screens))
    elif deleted_screens:
        module.exit_json(changed=True, result="Successfully deleted screen(s): %s" % ",".join(deleted_screens))
    else:
        module.exit_json(changed=False)


if __name__ == '__main__':
    main()
