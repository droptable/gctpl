import sys
import re
import argparse

class Util:
  # 1. whole placeholder, 2. name with delimiter, 3. name, 4. whole format, 5. flags, 6. padding, 7. type
  re_args = r'(\{(([^:]+):)(%([-+]?)([0-9]{0,})(\w))\})'
  re_def_delim = r'[\n]{2}'
  re_def_name = r'^(\w[a-zA-Z0-9_]{1,})\:[\n\s\t]+'
  re_def_data = r'([\s\t]{2,})|([\n])'

  format_translation_table = {
    'u': 'unsigned int',
    'i': 'int',
    'd': 'int',
    
    'ul': 'unsigned long',
    'l': 'long',

    'f': 'float',

    'c': 'char',
    's': 'char*'
  }

class Definition:
  definitions = []

  def __init__(self, name, data):
    self.name = name
    self.data = data
    self.args = {'order': []}

    for arg in re.findall(Util.re_args, data): # Currently not working
      self.args['order'].append(arg[2])

      self.args[arg[2]] = {
        'type': Util.format_translation_table[arg[6]],
        'format': arg[3]
      }

      self.data = re.sub(arg[0], arg[3], self.data)

    Definition.definitions.append(self)

  def is_function(self):
    return len(self.args) > 1

  def is_constant(self):
    return self.is_function() is not True

class Template:
  templates = []

  def __init__(self, path):
    self.path = path

    with open(self.path, "r", encoding="utf-8") as input:
      self.data = input.read()

    Template.templates.append(self)

class Parser:
  def parse(self):
    for template in Template.templates:
      self.parse_file(template)

  def parse_file(self, template):
    definitions = re.split(Util.re_def_delim, template.data)

    for definition in definitions:
      name = None
      offset = 0

      while offset < len(definition):
        if definition[offset] in [' ', '\t', '\n']: # spaces
          offset += 1

        elif definition[offset] is '#': # comment
          offset += definition[offset:].find('\n')

        elif name is None: # definition name
          name = re.search(Util.re_def_name, definition[offset:])

          if name is None:
            print ("ERROR: Could not parse '" + template.path + "'. Quitting.")
            sys.exit(1)

          offset += len(name.group(0))
          name = name.group(1)

        else: # definition data
          # currently not working - removes some bits not wanted to be removed
          data = re.sub(Util.re_def_data, r' ', definition[offset:])
          
          Definition(name, data)
          break

class Builder:
  def __init__(self, args):
    self.args = args

  def write(self):
    self.write_header()
    self.write_source()

  def write_header(self):
    with open(self.args.output[0] + '.' + self.args.extensions[0], "w", encoding="utf-8") as hfs:
      hfs.write('#pragma once\n\n')
      
      for definition in [x for x in Definition.definitions if x.is_constant() == True]:
        hfs.write(self.generate_constant(definition) + "\n")

      for definition in [x for x in Definition.definitions if x.is_function() == True]:
        if self.args.context_args == True:
          hfs.write(self.generate_function_contexts(definition) + "\n")

        hfs.write(self.generate_function_head(definition) + ";\n")

  def write_source(self):
    function_defintions = [x for x in Definition.definitions if x.is_function() == True]

    if function_defintions is None:
      return

    with open(self.args.output[0] + '.' + self.args.extensions[1], "w", encoding="utf-8") as sfs:
      sfs.write('#include <stdio.h>\n')
      
      for inc_lib in self.args.include_libs:
        sfs.write('#include "' + inc_lib + '"\n')

      sfs.write('#include "' + self.args.output[0][self.args.output[0].find('/')+1:] + '.' + self.args.extensions[0] + '"\n\n')

      for definition in function_defintions:
        sfs.write(self.generate_function_head(definition) + "\n{\n")
        sfs.write(self.generate_function_body(definition) + "\n")
        sfs.write('}\n\n')

  def generate_name(self, definition, render_prefix='render_'):
    def_type = ''
    def_name = self.args.prefix[0]

    if definition.is_function():
      def_type = 'function'
      def_name += render_prefix

    elif definition.is_constant():
      def_type = 'constant'

    def_name += definition.name

    if def_type in self.args.uppercase:
      return def_name.upper()

    return def_name.lower()

  def generate_definition_data(self, definition, indentation='    '):
    chunk_len = self.args.max_len - (5 + len(indentation))
    
    data = re.sub(r'"', r'\\"', definition.data)
    data = [indentation + '"' + data[i:chunk_len+i] + '"'  for i in range(0, len(data), chunk_len)]

    return ' \\\n'.join(data)

  def generate_constant(self, definition):
    cnst = '#define ' + self.generate_name(definition) + ' \\\n'

    cnst += self.generate_definition_data(definition) + '\n'

    return cnst

  def generate_function_contexts(self, definition):
    ctx_def = 'struct ' + self.generate_name(definition, '') + '_ctx\n{\n'

    for arg_name in definition.args.keys():
      if arg_name is 'order':
        continue 

      ctx_def += '  ' + definition.args[arg_name]['type'] + ' ' + arg_name + ';\n'

    return ctx_def + '};\n'

  def generate_function_head(self, definition):
    func_def = 'void ' + self.generate_name(definition) + '('

    if self.args.context_args == True:
      func_def += 'struct ' + self.generate_name(definition, '') + '_ctx *tpl_ctx'

    else:
      function_args = [definition.args[arg_name]['type'] + ' ' + arg_name  for arg_name in sorted(definition.args) if arg_name is not 'order']
      func_def += ', '.join(function_args)

    return func_def + ')'

  def generate_function_body(self, definition):
    arg_prefix = ''
    func_body = '  const char *format = \n' + self.generate_definition_data(definition) + ';\n\n'

    func_body += '  if('

    if self.args.context_args == True:
      arg_prefix = 'tpl_ctx->'
      func_body += 'NULL == tpl_ctx'
    else:
      func_body += ' && '.join(['NULL == ' + arg_name for arg_name in definition.args if arg_name is not 'order' and definition.args[arg_name]['type'] == 'char*'])
      
    func_body += ')\n  {\n    return;\n  }\n\n'
    
    func_body += '  ' + self.args.render_func[0] + '(format, \n    '
    func_body += arg_prefix + (', \n    ' + arg_prefix).join(definition.args['order']) + '\n  );'

    return func_body

if __name__ == '__main__':
  consts = [{'name': '', 'args': [], 'definition': ''}]

  parser = argparse.ArgumentParser()

  parser.add_argument('-i', '--input', metavar="template", type=str, nargs='+', required=True, help="templates to be translated")
  parser.add_argument('-o', '--output', metavar="file", type=str, nargs=1, required=True, help="translated file path and name, extension ignored if set")
  parser.add_argument('-p', '--prefix', metavar="prefix", type=str, nargs=1, required=False, default=[''], help="prefix used for structs, constants and functions")
  parser.add_argument('-e', '--extensions', metavar=("header-ext", "source-ext"), type=str, nargs=2, required=False, default=('h', 'c'), help="file extensions for output files (default: %(default)s)")
  parser.add_argument('-u', '--uppercase', metavar="type", default=("function", "constant"), nargs='+', type=str, help="set idents to uppercase format (default: %(default)s. values are: function, constant. more than one value possible")
  parser.add_argument('-m', '--max-len', metavar="max-length", default=80, nargs=1, type=int, help="maximum line length")
  parser.add_argument('-c', '--context-args', action="store_const", const=True, default=False, help="use context struct as render function argument")
  parser.add_argument('-r', '--render-func', metavar="function-name", nargs=1, required=False, type=str, default=["printf"], help="which function to use for rendering (default: %(default)s)")
  parser.add_argument('-l', '--include-libs', metavar="include-file", nargs='+', required=False, type=str, help="include multiple files")

  args = parser.parse_args()

  for tfp in args.input:
    Template(tfp)

  Parser().parse()
  Builder(args).write()

  sys.exit(0)
