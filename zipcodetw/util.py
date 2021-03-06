#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

class Address(object):

    TOKEN_RE = re.compile(u'''
        (?:
            (?P<no>\d+)
            (?P<subno>之\d+)?
            (?=[巷弄號樓])
            |
            (?P<name>\d|.{2,}?)
        )
        (?:
            (?P<unit>[縣市鄉鎮市區村里鄰路街段巷弄號樓])
            |
            (?=\d+(?:之\d+)?[巷弄號樓]|$)
        )
    ''', re.X)

    NO    = 0
    SUBNO = 1
    NAME  = 2
    UNIT  = 3

    TO_REPLACE_RE = re.compile(u'''
        ^[\u0000-\u007F]+
        |
        [台臺]灣省?(?!大道|港務)
        |
        [ 　,，台~-]
        |
        (?<![臺台新竹])北市(?!場)
        |
        [０-９]
        |
        [一二三四五六七八九]?
        十?
        [一二三四五六七八九]
        (?=[段路街巷弄號樓])
    ''', re.X)

    # the strs to replace not in here will be removed
    TO_REPLACE_MAP = {
        u'-': u'之', u'~': u'之', u'台': u'臺', u'北市': u'臺北市',
        u'１': u'1', u'２': u'2', u'３': u'3', u'４': u'4', u'５': u'5',
        u'６': u'6', u'７': u'7', u'８': u'8', u'９': u'9', u'０': u'0',
        u'一': u'1', u'二': u'2', u'三': u'3', u'四': u'4', u'五': u'5',
        u'六': u'6', u'七': u'7', u'八': u'8', u'九': u'9',
    }

    CHINESE_NUMERALS_SET = set(u'一二三四五六七八九十')

    @staticmethod
    def normalize(s):

        if isinstance(s, str):
            s = s.decode('utf-8')

        def replace(m):

            found = m.group()

            if found in Address.TO_REPLACE_MAP:
                return Address.TO_REPLACE_MAP[found]

            # for '十一' to '九十九'
            if found[0] in Address.CHINESE_NUMERALS_SET:

                len_found = len(found)

                if len_found == 2:
                    return u'1'+Address.TO_REPLACE_MAP[found[1]]
                if len_found == 3:
                    return Address.TO_REPLACE_MAP[found[0]]+Address.TO_REPLACE_MAP[found[2]]

            return u''

        s = Address.TO_REPLACE_RE.sub(replace, s)

        return s

    @staticmethod
    def tokenize(addr_str):
        return tuple(Address.TOKEN_RE.findall(Address.normalize(addr_str)))

    def __init__(self, addr_str):
        self.tokens = Address.tokenize(addr_str)

    def __len__(self):
        return len(self.tokens)

    def flat(self, sarg=None, *sargs):
        return u''.join(u''.join(token) for token in self.tokens[slice(sarg, *sargs)])

    def pick_to_flat(self, *idxs):
        return u''.join(u''.join(self.tokens[idx]) for idx in idxs)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.flat())

    def parse(self, idx):
        try:
            token = self.tokens[idx]
        except IndexError:
            return (0, 0)
        else:
            return (
                int(token[Address.NO]        or 0),
                int(token[Address.SUBNO][1:] or 0)
            )

class StandardAddress(Address):

    LEVEL_UNITS_LIST = [u'縣市', u'區市鎮鄉', u'路街里']

    def __init__(self, addr_str):

        Address.__init__(self, addr_str)
        len_tokens = len(self.tokens)

        standard_tokens = []

        start_pos = 0
        for units in StandardAddress.LEVEL_UNITS_LIST:
            for unit in units:
                for i in range(start_pos, len_tokens):
                    if self.tokens[i][Address.UNIT] == unit:
                        standard_tokens.append(self.tokens[i])
                        start_pos = i+1
                        break
                else:
                    continue # if not found
                break

        self.tokens = tuple(standard_tokens+list(self.tokens[start_pos:]))

class Rule(Address):

    RULE_TOKEN_RE = re.compile(u'''
        及以上附號|含附號以下|含附號全|含附號
        |
        以下|以上
        |
        附號全
        |
        [連至單雙全](?=[\d全]|$)
    ''', re.X)

    @staticmethod
    def part(rule_str):

        rule_str = Address.normalize(rule_str)

        rule_tokens = set()

        def extract(m):

            token = m.group()
            retval = u''

            if token == u'連':
                token = u''
            elif token == u'附號全':
                retval = u'號'

            if token:
                rule_tokens.add(token)

            return retval

        addr_str = Rule.RULE_TOKEN_RE.sub(extract, rule_str)

        return (rule_tokens, addr_str)

    def __init__(self, rule_str):
        self.rule_tokens, addr_str = Rule.part(rule_str)
        Address.__init__(self, addr_str)

    def __repr__(self):
        return 'Rule(%r)' % (self.flat()+u''.join(self.rule_tokens))

    def match(self, addr):

        # except tokens reserved for rule token

        my_last_pos = len(self.tokens)-1
        my_last_pos -= bool(self.rule_tokens) and u'全' not in self.rule_tokens
        my_last_pos -= u'至' in self.rule_tokens

        # tokens must be matched exactly

        if my_last_pos >= len(addr.tokens):
            return False

        i = my_last_pos
        while i >= 0:
            if self.tokens[i] != addr.tokens[i]:
                return False
            i -= 1

        # check the rule tokens

        his_no_pair     = addr.parse(my_last_pos+1)
        if self.rule_tokens and his_no_pair == (0, 0):
            return False

        my_no_pair      = self.parse(-1)
        my_asst_no_pair = self.parse(-2)
        for rt in self.rule_tokens:
            if (
                (rt == u'單'         and not his_no_pair[0] & 1 == 1) or
                (rt == u'雙'         and not his_no_pair[0] & 1 == 0) or
                (rt == u'以上'       and not his_no_pair >= my_no_pair) or
                (rt == u'以下'       and not his_no_pair <= my_no_pair) or
                (rt == u'至'         and not (
                    my_asst_no_pair <= his_no_pair <= my_no_pair or
                    u'含附號全' in self.rule_tokens and his_no_pair[0] == my_no_pair[0]
                )) or
                (rt == u'含附號'     and not  his_no_pair[0] == my_no_pair[0]) or
                (rt == u'附號全'     and not (his_no_pair[0] == my_no_pair[0] and his_no_pair[1] > 0)) or
                (rt == u'及以上附號' and not  his_no_pair >= my_no_pair) or
                (rt == u'含附號以下' and not (his_no_pair <= my_no_pair  or his_no_pair[0] == my_no_pair[0]))
            ):
                return False

        return True

import sqlite3
import csv
from functools import wraps

class Directory(object):

    @staticmethod
    def get_common_part(str_a, str_b):

        if str_a is None: return str_b
        if str_b is None: return str_a

        i = 0 # for the case range is empty
        for i in range(min(len(str_a), len(str_b))):
            if str_a[i] != str_b[i]:
                break
        else:
            i += 1

        return str_a[:i]

    def __init__(self, db_path, keep_alive=False):
        self.db_path = db_path
        # It will always use a same connection if keep_alive is true.
        self.keep_alive = keep_alive
        self.conn = None
        self.cur = None

    def create_tables(self):

        self.cur.execute('''
            create table precise (
                addr_str text,
                rule_str text,
                zipcode  text,
                primary key (addr_str, rule_str)
            );
        ''')

        self.cur.execute('''
            create table gradual (
                addr_str text primary key,
                zipcode  text
            );
        ''')

    def put_precise(self, addr_str, rule_str, zipcode):

        self.cur.execute('insert or ignore into precise values (?, ?, ?);', (
            addr_str,
            rule_str,
            zipcode
        ))

        return self.cur.rowcount

    def put_gradual(self, addr_str, zipcode):

        self.cur.execute('''
            select zipcode
            from   gradual
            where  addr_str = ?;
        ''', (addr_str,))

        row = self.cur.fetchone()
        if row is None:
            stored_zipcode = None
        else:
            stored_zipcode = row[0]

        self.cur.execute('replace into gradual values (?, ?);', (
            addr_str,
            Directory.get_common_part(stored_zipcode, zipcode),
        ))

        return self.cur.rowcount

    def put(self, head_addr_str, tail_rule_str, zipcode):

        addr = Address(head_addr_str)

        # (a, b, c)

        self.put_precise(
            addr.flat(),
            head_addr_str+tail_rule_str,
            zipcode
        )

        # (a, b, c) -> (a,); (a, b); (a, b, c); (b,); (b, c); (c,)

        len_tokens = len(addr)
        for f in range(len_tokens):
            for l in range(f, len_tokens):
                self.put_gradual(
                    addr.flat(f, l+1),
                    zipcode
                )

        if len_tokens >= 3:
            # (a, b, c, d) -> (a, c)
            self.put_gradual(addr.pick_to_flat(0, 2), zipcode)

    def within_a_transaction(method):

        @wraps(method)
        def method_wrapper(self, *args, **kargs):

            if not self.keep_alive or self.conn is None:
                self.conn = sqlite3.connect(self.db_path)
            self.cur = self.conn.cursor()

            try:
                retval = method(self, *args, **kargs)
            except:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()
            finally:
                self.cur.close()
                if not self.keep_alive:
                    self.conn.close()

            return retval

        return method_wrapper

    @within_a_transaction
    def load_chp_csv(self, chp_csv_lines):

        self.create_tables()

        lines_iter = iter(chp_csv_lines)
        next(lines_iter)

        for row in csv.reader(lines_iter):
            self.put(
                ''.join(row[1:-1]).decode('utf-8'),
                row[-1].decode('utf-8'),
                row[0].decode('utf-8'),
            )

    def get_rule_str_zipcode_pairs(self, addr_str):

        self.cur.execute('''
            select rule_str, zipcode
            from   precise
            where  addr_str = ?;
        ''', (addr_str,))

        return self.cur.fetchall()

    def get_gradual_zipcode(self, addr_str):

        self.cur.execute('''
            select zipcode
            from   gradual
            where  addr_str = ?;
        ''', (addr_str,))

        row = self.cur.fetchone()
        return row and row[0] or None

    @within_a_transaction
    def find(self, addr_str):

        addr = StandardAddress(addr_str)

        for i in range(len(addr.tokens), 0, -1):

            addr_str = addr.flat(i)

            rzpairs = self.get_rule_str_zipcode_pairs(addr_str)

            if rzpairs:
                for rule_str, zipcode in rzpairs:
                    if Rule(rule_str).match(addr):
                        return zipcode

            gzipcode = self.get_gradual_zipcode(addr_str)
            if gzipcode:
                return gzipcode

        return u''
