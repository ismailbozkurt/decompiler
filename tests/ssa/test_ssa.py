
import unittest
import sys
sys.path.append('../')
sys.path.append('../../src/')

from common.ply import ir_parser
from common.disassembler import parser_disassembler
import decompiler
from decompiler import decompiler_t
from output import c
import ssa

class TestSSA(unittest.TestCase):

  def assert_ssa_form(self, input, expected):

    ssa.ssa_context_t.index = 0
    dis = parser_disassembler(input)
    d = decompiler_t(dis, 0)

    for step in d.steps():
      print 'Decompiler step: %u - %s' % (step, decompiler_t.phase_name[step])
      if step >= decompiler.STEP_SSA_DONE:
        break

    t = c.tokenizer(d.flow)
    tokens = list(t.flow_tokens())

    result = ''.join([str(t) for t in tokens])

    assert result == expected, 'SSA form is not as expected.\n\nExpected:\n%s\n\nGot:\n%s' % (expected, result)

    return

  def assert_ssa_aliases(self, input, expected):

    ssa.ssa_context_t.index = 0
    dis = parser_disassembler(input)
    d = decompiler_t(dis, 0)

    for step in d.steps():
      print 'Decompiler step: %u - %s' % (step, decompiler_t.phase_name[step])
      if step >= decompiler.STEP_SSA_DONE:
        break

    map = {}

    for left, right in d.ssa_tagger.aliases.iteritems():

      t = c.tokenizer(d.flow)
      tokens = list(t.expression_tokens(left))
      left = ''.join([str(t) for t in tokens])

      tokenized = []
      for expr in right:
        t = c.tokenizer(d.flow)
        tokens = list(t.expression_tokens(expr))
        right = ''.join([str(t) for t in tokens])
        tokenized.append(right)

      map[left] = tokenized

    result = repr(map)
    assert result == expected, 'SSA form is not as expected.\n\nExpected:\n%s\n\nGot:\n%s' % (expected, result)

    return

  def test_normal_regs(self):
    """ Test proper renaming of all register locations. """

    input = """
      a = 1;
      b = 2;
      a = a + b;
      return a;
    """

    expected = """
    func() {
      a@0 = 1;
      b@1 = 2;
      a@2 = a@0 + b@1;
      return a@2;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_normal_deref(self):
    """ Test proper renaming of all dereference locations. """

    input = """
      *(s+4) = 1;
      *(s+8) = 2;
      *(s+4) = *(s+4) + *(s+8);
      return *(s+4);
    """
    expected = """
    func() {
      *(s@0 + 4)@1 = 1;
      *(s@0 + 8)@2 = 2;
      *(s@0 + 4)@3 = *(s@0 + 4)@1 + *(s@0 + 8)@2;
      return *(s@0 + 4)@3;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_alias_deref(self):
    """ Check that *(a + 8) and *(s + 4) are correctly aliased and get the same index. """

    input = """
      a = s;
      *(a + 8) = 1;
      s = s + 4;
      return *(s + 4);
    """

    expected = """
    func() {
      a@1 = s@0;
      *(a@1 + 8)@3 = 1;
      s@2 = s@0 + 4;
      return *(s@2 + 4)@3;
    }
    """

    aliases = {'*(s@0 + 8)': ['*(a@1 + 8)', '*(s@2 + 4)']}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_if_1(self):
    """ Test inclusion of theta functions in simple 'if' block.

    a = 1;
    if (b == 0)
      a = 2;
    return a;
    """

    input = """
          a = 1;
          if (b != 0) goto 300;
          a = 2;
    300:  return a;
    """

    expected = """
    func() {
      a@0 = 1;
      goto loc_3 if(b@1 != 0) else goto loc_2;

    loc_3:
      a@2 = THETA(a@0, a@3, );
      return a@2;

    loc_2:
      a@3 = 2;
      goto loc_3;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_if_2(self):
    """ Test inclusion of theta functions in simple 'if-then-else' block.

    if (a == 0)
      a = 1;
    else
      a = 2;
    return a;
    """

    input = """
          if (a == 0) goto 200;
          a = 2;
          goto 300;
    200:  a = 1;
    300:  return a;
    """

    expected = """
    func() {
      goto loc_3 if(!(a@0)) else goto loc_1;

    loc_3:
      a@1 = 1;
      goto loc_4;

    loc_1:
      a@3 = 2;
      goto loc_4;

    loc_4:
      a@2 = THETA(a@1, a@3, );
      return a@2;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_while(self):
    """ Test inclusion of theta functions in simple 'while' loop.

    i = 0;
    while (i < 100) {
      i = i + 1;
    }
    return i;
    """

    input = """
          i = 0;
    100:  if (i >= 100) goto 400;
          i = i + 1;
          goto 100;
    400:  return i;
    """

    expected = """
    func() {
       i@0 = 0;
       goto loc_1;

    loc_1:
       i@1 = THETA(i@0, i@4, );
       goto loc_4 if(i@1 >= 100) else goto loc_2;

    loc_4:
       i@2 = THETA(i@1, );
       return i@2;

    loc_2:
       i@3 = THETA(i@1, );
       i@4 = i@3 + 1;
       goto loc_1;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_do_while(self):
    """ Test inclusion of theta functions in simple 'do-while' loop.

    i = 0;
    do {
      i = i + 1;
    } while (i < 100);
    return i;
    """

    input = """
          i = 0;
    200:  i = i + 1;
          if (i < 100) goto 200;
          return i;
    """

    expected = """
    func() {
      i@0 = 0;
      goto loc_1;

    loc_1:
      i@1 = THETA(i@0, i@2, );
      i@2 = i@1 + 1;
      goto loc_1 if(i@2 < 100) else goto loc_3;

    loc_3:
      i@3 = THETA(i@2, );
      return i@3;
    }
    """

    aliases = {}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_deref_do_while(self):
    """ Test inclusion of theta functions in 'do-while' loop with dereferences.

    *(i) = 0;
    do {
        *(i) = *(i) + 1;
    } while (*(i) < 100);
    return *(i);
    """

    input = """
          *(i) = 0;
    200:  *(i) = *(i) + 1;
          if (*(i)< 100) goto 200;
          return *(i);
    """

    expected = """
    func() {
      *(i@0)@3 = 0;
      goto loc_1;

    loc_1:
      i@1 = THETA(i@0, );
      *(i@1)@4 = THETA(*(i@0)@3, *(i@1)@5, );
      *(i@1)@5 = *(i@1)@4 + 1;
      goto loc_1 if(*(i@1)@5 < 100) else goto loc_3;

    loc_3:
      i@2 = THETA(i@1, );
      *(i@2)@6 = THETA(*(i@1)@5, );
      return *(i@2)@6;
    }
    """

    aliases = {'*(i@0)': ['*(i@1)', '*(i@2)']}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_deref_do_while_2(self):
    """ Test inclusion of theta functions in simple 'do-while' loop.

    *(i) = 0;
    do {
      *(i) = *(i) + 1;
    } while (*(i) < 100);
    return *(i);
    """

    input = """
          *(i) = 0;
    200:  i = i + 1;
          *(i) = *(i) + 1;
          if (*(i)< 100) goto 200;
          return *(i);
    """

    expected = """
    func() {
      *(i@0)@4 = 0;
      goto loc_1;

    loc_1:
      i@1 = THETA(i@0, i@2, );
      *(i@1)@5 = THETA(*(i@0)@4, *(i@1)@6, );
      i@2 = i@1 + 1;
      *(i@2)@6 = *(i@2)@5 + 1;
      goto loc_1 if(*(i@2)@6 < 100) else goto loc_4;

    loc_4:
      i@3 = THETA(i@2, );
      *(i@3)@7 = THETA(*(i@1)@6, );
      return *(i@3)@7;
    }
    """

    aliases = {'*(i@0 + 1)': ['*(i@2)', '*(i@3)'], '*(i@0)': ['*(i@1)']}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_deref_1(self):
    """ Test inclusion of theta functions for dereferences in simple 'if' block.

    if (*(s+4) == 0)
        *(s+4) = 1;
    return *(s+4);
    """

    input = """
          if(*(s+4) == 0) goto 300;
          *(s+4) = 1;
    300:  return *(s+4);
    """

    expected = """
    func() {
      goto loc_2 if(!(*(s@0 + 4)@3)) else goto loc_1;

    loc_2:
      s@1 = THETA(s@0, s@2, );
      *(s@1 + 4)@4 = THETA(*(s@0 + 4)@3, *(s@2 + 4)@5, );
      return *(s@1 + 4)@4;

    loc_1:
      s@2 = THETA(s@0, );
      *(s@2 + 4)@5 = 1;
      goto loc_2;
    }
    """

    aliases = {'*(s@0 + 4)': ['*(s@2 + 4)', '*(s@1 + 4)']}

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

  def test_theta_deref_2(self):
    """ Test inclusion of theta functions for dereferences with aliasing in 'if' block: *(s + 8), *(a + c) and *(a + 4) should be correctly aliased and get theta-functions.

    a = s + 4;
    if (*(s + 8) == 0) {
        c = 4;
        *(a + c) = *(s + 8) + 1;
    }
    return *(a + 4);
    """

    input = """
          a = s + 4;
          if (*(s + 8) != 0) goto 300;

          c = 4;
          *(a + c) = *(s + 8) + 1;

    300:  return *(a + 4);
    """

    expected = """
    func() {
      a@1 = s@0 + 4;
      goto loc_4 if(*(s@0 + 8)@6 != 0) else goto loc_2;

    loc_4:
      a@2 = THETA(a@1, a@4, );
      *(a@2 + 4)@7 = THETA(*(s@0 + 8)@6, *(a@4 + c@3)@9, );
      return *(a@2 + 4)@7;

    loc_2:
      c@3 = 4;
      a@4 = THETA(a@1, );
      s@5 = THETA(s@0, );
      *(s@5 + 8)@8 = THETA(*(s@0 + 8)@6, );
      *(a@4 + c@3)@9 = *(s@5 + 8)@8 + 1;
      goto loc_4;
    }
    """

    aliases = {
      '*(s@5 + 8)@8': ['*(s@0 + 8)'],
      '*(a@2 + 4)@7': ['*(s@0 + 8)'],
      '*(a@4 + c@3)@9': ['*(s@0 + 8)'],
      '*(s@0 + 8)@6': ['*(s@0 + 8)']
    }

    self.assert_ssa_form(input, expected)
    self.assert_ssa_aliases(input, repr(aliases))
    return

if __name__ == '__main__':
  unittest.main()
