/* Ansible Dynamic Inventory

This simple program generates an Ansible dynamic inventory by utilizing the information in the 'hosts.ini' 
file located in the current directory. It meticulously considers all the variables defined in the standard 
'group_vars' and 'host_vars' folders, ensuring complete compatibility with Ansible's default configuration.

Compile in Linux:
    gcc inventory.c -ljansson

Official Ansible documentation: <https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html> 

TODO: 
- parse_hosts_ini()
    - parse groups and hosts in groups
    - parse ini ranges. Example:
        [databases]
        db-[a:f].example.com
        www[01:50].example.com
        www[01:50:2].example.com

- other functions
    - parse "host_vars" folders
    - parse "group_vars" folder
- host() function
*/
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <string.h>
#include <jansson.h> // A third-party library for JSON encoding and decoding in C

void help() {
    char* help_message = 
        "Usage: options [OPTION]\n"
        "\n"
        "  -h, --help          Display this help and exit\n"
        "  -l, --list          Returns a JSON encoded inventory dictionary\n"
        "  -H, --host hostname Returns a JSON encoded dictionary for 'hostname' variables\n"
        "\n";
    printf("%s", help_message);
}

// return a dictionary from a JSON object, fond using it's name
json_t *find_dict(const json_t *root_obj, const char *keyname) {
    // init output object
    json_t *output_dict = json_object();

    // return the value if it's a string from key:value pairs
    json_t *string_value = json_object_get(root_obj, keyname);
    if (json_string_value(string_value)) {
        printf("str value: %s\n", json_string_value(string_value));
        //return string_value;
    }
    return output_dict;
}

/* return an JSON object from a *.ini string that may contain values. 
*.ini string examples
1. just_a_key
2. a_key_with_values subkey1=value1 subkey2=value2

Return values:
1. {
    "hostname": "just_a_key"
}

2. {
    "hostname": "a_key_with_values",
    "vars": {
        "subkey1": "value1",
        "subkey2": "value2"
    }
}
*/
json_t *convert_ini_line(char *ini_string) {
    json_t *return_obj = json_object(); // main object
    char *rest; // pointer to string left after spliting

    // split the string containgin spaces and save first value as the 'key' rest to &rest
    char * key = strtok_r(ini_string, " ", &rest);
    
    // add the hostname to the object
    json_object_set_new(return_obj, "hostname", json_string(key));

    // check if the ini_string contains extra values, return the object if not
    if(!strcmp(rest, ""))
        return return_obj;

    // Init the the 'vars' dict and pointers
    json_t *vars_obj = json_object();
    char *value_ptr, *key_ptr = NULL;

    // loop through 'key=value' pair and add them to 'vars' dict
    while (key_ptr = strtok_r(rest, " ", &rest)) {

        // copy key_ptr to key and strip it accoridingly
        char *key = malloc(strlen(key_ptr));
        strcpy(key, key_ptr);
        key = strtok(key, "=");

        // get the value
        value_ptr = strchr(key_ptr, '=');
        if (value_ptr) {
            // got a key=value pair, move away from '=' in value_ptr
            *value_ptr = '\0';
            value_ptr++;
            json_object_set_new(vars_obj, key, json_string(value_ptr));
        } else {
            // only key, no value
            json_object_set_new(vars_obj, key, json_string(""));
        }
    }

    // Add the the 'vars' dict
    json_object_set_new(return_obj, "vars", vars_obj);
    return return_obj;
}

/* return the inventory list as a JSON object in form:
{
    "_meta": {
      "hostvars": {}
    },
    "all": {
      "children": [
        "ungrouped"
      ]
    },
    "ungrouped": {
      "hosts": []
    }
}
*/
json_t *parse_hosts_ini(const char *filename) {

    // define and initiate default dictionaries
    json_t *root = json_object();
    json_t *meta = json_object();
    json_t *all = json_object();
    json_t *all_children = json_array();
    json_t *ungrouped = json_object();
    json_t *ungrouped_hosts = json_array();
    json_t *hostvars = json_object();

    // create the default JSON object
    json_array_append_new(all_children, json_string("ungrouped"));
    json_object_set_new(all, "children", all_children);
    json_object_set_new(ungrouped, "hosts", ungrouped_hosts);
    json_object_set_new(meta, "hostvars", hostvars);
    json_object_set_new(root, "_meta", meta);
    json_object_set_new(root, "all", all);
    json_object_set_new(root, "ungrouped", ungrouped);


    // Read the .ini file
    FILE *ini_file;
    char *line = NULL;
    size_t buffer_length = 0; // size of the buffer
    ssize_t read_chars; // number of characters read (ssize_t is signed integer)

    ini_file = fopen(filename, "r");
    if (ini_file == NULL) 
        return json_object(); // empty object

    json_t *line_as_json, *vars, *hostname; // a converted line, vars and hostname variables

    int groups_flag = 0; // flag to read all ungrouped entries
    while ((read_chars = getline(&line, &buffer_length, ini_file)) != -1 ) {
        // remove the '\n's
        if (line[strlen(line) - 1] == '\n')
            line[strlen(line) - 1] = '\0';

        // ignore empty lines
        if (line[0] == '\0')
            continue;

        // collect the ungrouped entries
        if (!groups_flag && line[0] == '[') {
            groups_flag++;
        }

        if (!groups_flag) {
            line_as_json = convert_ini_line(line);

            // get the hostname and add it to ungrouped_hosts obj
            hostname = json_object_get(line_as_json, "hostname");
            json_array_append(ungrouped_hosts, hostname);

            // get the vars dict and add them to _meta -> hostvars
            vars = json_object_get(line_as_json, "vars");
            if (vars) 
                json_object_set_new(hostvars,  json_string_value(hostname), vars);
            
        }
        else {
            // Here start the groups in the .ini file

            // get the section
            if (line[0] == '[') {
                char *group_name = line + 1;
                char *rest = strchr(group_name, ']');
                char *sub_group;

                // get sub group, if any
                if (rest) {
                    *rest = '\0';
                    sub_group = strchr(group_name, ':');
                    if (sub_group) {
                        // strip ':'
                        *sub_group = '\0';
                        sub_group++;
                    }
                }

                // get the group object, if not add a new one
                json_t *group = json_object_get(root, group_name);
                if (!group) {
                    group = json_object();
                    json_object_set_new(root, group_name, group);
                    json_array_append_new(all_children, json_string(group_name));
                }

                // add vars to meta, if any
                if (sub_group && !strcmp(sub_group, "vars")) {
                    printf("Got vars in %s: %s\n", group_name, sub_group);
                }

                // add children to group if any
                if (sub_group && !strcmp(sub_group, "children")) {
                    printf("Got children in %s: %s\n", group_name, sub_group);
                }

                continue;
            }
            printf("=-Not parsed: %s\n", line);
        }
    }

    free(line);
    fclose(ini_file);

    return root;
}

const char *host(char *hostname, json_t *root_json) {
    // returns a hostname dictionary from a JSON object 

    // init en empty output JSON dictionary, and a char pointer for return value
    json_t *output_dict = json_object();
    char *output; 

    // test find_dict()
    output_dict = find_dict(root_json, hostname);

    // return the output dictionary 
    output = json_dumps(output_dict, JSON_INDENT(2));
    json_decref(output_dict);
    return output;
}

int main(int argc, char *argv[]) {

    const char *ini_filename = "hosts.ini";

    if (argc <= 1) {
        help();
        return 0;
    }

    if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        help();
        return 0;
    } 

    // Execute for valid options
    char *valid_options[] = {"-l", "-H", "--list", "--host"};
    size_t arr_length = sizeof(valid_options)/sizeof(valid_options[0]);

    for (size_t i = 0; i < arr_length; ++i) {
        if (!strcmp(valid_options[i], argv[1])) {

            // JSON root object
            json_t *root;
            root = parse_hosts_ini(ini_filename);
            if (!root) {
                printf("Failed to read %s\n", ini_filename);
                return 1;
            }
            
            // execute the --list command
            if (strcmp(argv[1], "--list") == 0 || strcmp(argv[1], "-l") == 0) {
                char *json_str;
                json_str = json_dumps(root, JSON_INDENT(2));
                printf("%s\n", json_str);
                free(json_str);
            }

            // execute the --host command
            if (strcmp(argv[1], "--host") == 0 || strcmp(argv[1], "-H") == 0) {
                if (argc > 2) {
                    printf("%s\n", host(argv[2], root));
                } else {
                    printf("Error: Missing hostname argument\n");
                    help();
                }
            }
            json_decref(root);
            return 0;
        }
    }

    printf("Error: Unkown options provided\n");
    help();
    return 1;
}
