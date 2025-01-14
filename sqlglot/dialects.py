# pylint: disable=no-member
import sqlglot.expressions as exp
from sqlglot.generator import Generator
from sqlglot.helper import RegisteringMeta
from sqlglot.parser import Parser
from sqlglot.tokens import Tokenizer, TokenType


class Dialect(metaclass=RegisteringMeta):
    identifier = None
    quote = None
    functions = {}
    transforms = {}

    def parse(self, code):
        return self.parser().parse(self.tokenizer().tokenize(code), code)

    def generate(self, expression, **opts):
        return self.generator(**opts).generate(expression)

    def transpile(self, code, **opts):
        return self.generate(self.parse(code), **opts)

    def generator(self, **opts):
        return Generator(**{
            'identifier': self.identifier,
            'quote': self.quote,
            'transforms': {**self.transforms, **opts.pop('transforms', {})},
            **opts,
        })

    def parser(self, **opts):
        return Parser(functions=self.functions, **opts)

    def tokenizer(self, **opts):
        return Tokenizer(identifier=self.identifier, quote=self.quote, **opts)


class Hive(Dialect):
    identifier = '`'

    def _approx_distinct_sql(self, expression):
        if expression.args.get('accuracy'):
            self.unsupported('APPROX_COUNT_DISTINCT does not support accuracy')
        return f"APPROX_COUNT_DISTINCT({self.sql(expression, 'this')})"

    def _fileformat_sql(self, expression):
        file_format = self.sql(expression, 'this').replace(self.quote, '')
        if file_format:
            return F"STORED AS {file_format}"
        return ''

    transforms = {
        exp.ApproxDistinct: _approx_distinct_sql,
        exp.FileFormat: _fileformat_sql,
        exp.JSONPath: lambda self, e: f"GET_JSON_OBJECT({self.sql(e.args['this'])}, {self.sql(e.args['path'])})",
    }

    functions = {
        'APPROX_COUNT_DISTINCT': lambda args: exp.ApproxDistinct(this=args[0]),
        'GET_JSON_OBJECT': lambda args: exp.JSONPath(this=args[0], path=args[1]),
    }


class MySQL(Dialect):
    identifier = '`'


class Postgres(Dialect):
    transforms = {
        TokenType.TINYINT: 'SMALLINT',
        TokenType.FLOAT: 'REAL',
        TokenType.DOUBLE: 'DOUBLE PRECISION',
        TokenType.BINARY: 'BYTEA',
    }


class Presto(Dialect):
    def _approx_distinct_sql(self, expression):
        accuracy = expression.args.get('accuracy')
        accuracy = ', ' + self.sql(accuracy) if accuracy else ''
        return f"APPROX_DISTINCT({self.sql(expression, 'this')}{accuracy})"

    def _parse_approx_distinct(args):
        return exp.ApproxDistinct(
            this=args[0],
            accuracy=args[1] if len(args) > 1 else None,
        )

    def _fileformat_sql(self, expression):
        file_format = self.sql(expression, 'this').replace(self.quote, '')
        if file_format:
            return F"WITH (FORMAT = '{file_format}')"
        return ''

    transforms = {
        TokenType.INT: 'INTEGER',
        TokenType.FLOAT: 'REAL',
        TokenType.BINARY: 'VARBINARY',
        exp.ApproxDistinct: _approx_distinct_sql,
        exp.FileFormat: _fileformat_sql,
        exp.JSONPath: lambda self, e: f"JSON_EXTRACT({self.sql(e.args['this'])}, {self.sql(e.args['path'])})",
    }

    functions = {
        'APPROX_DISTINCT': _parse_approx_distinct,
        'JSON_EXTRACT': lambda args: exp.JSONPath(this=args[0], path=args[1]),
    }


class Spark(Hive):
    transforms = {
        **Hive.transforms,
        TokenType.TINYINT: 'BYTE',
        TokenType.SMALLINT: 'SHORT',
        TokenType.BIGINT: 'BIGINT',
        TokenType.CHAR: 'CHAR',
        TokenType.VARCHAR: 'VARCHAR',
        TokenType.TEXT: 'STRING',
        TokenType.BINARY: 'ARRAY[BYTE]',
        exp.Hint: lambda self, e: f" /*+ {self.sql(e, 'this').strip()} */",
    }

    functions = {
        'APPROX_COUNT_DISTINCT': lambda args: exp.ApproxDistinct(this=args[0]),
    }

    identifier = '`'

class MSAcess(Dialect):
    identifier = ('[',']')

class TSQL(Dialect):
    identifier = ('[',']')

class SQLite(Dialect):
    transforms = {
        TokenType.BOOLEAN: 'INTEGER',
        TokenType.TINYINT: 'INTEGER',
        TokenType.SMALLINT: 'INTEGER',
        TokenType.INT: 'INTEGER',
        TokenType.BIGINT: 'INTEGER',
        TokenType.FLOAT: 'REAL',
        TokenType.DOUBLE: 'REAL',
        TokenType.DECIMAL: 'REAL',
        TokenType.CHAR: 'TEXT',
        TokenType.VARCHAR: 'TEXT',
        TokenType.BINARY: 'BLOB',
    }
