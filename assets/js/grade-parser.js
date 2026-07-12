(function (root, factory) {
  'use strict';

  var parser = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = parser;
  }
  if (root) {
    root.GradeParser = parser;
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  var STATUS_VALUES = new Set([
    'NA', 'N/A', 'RE', 'AP', 'F', 'FALTOU', 'AUSENTE', 'DESISTIU',
    'ANULADO', 'ANULADA', 'EXCLUIDO', 'EXCLUIDA', 'DISPENSADO',
    'DISPENSADA', 'APROVADO', 'APROVADA', 'REPROVADO', 'REPROVADA',
    'PRESENTE', 'ADMITIDO', 'ADMITIDA'
  ]);

  var FEMALE_NAMES = new Set([
    'alexandra', 'amelia', 'ana', 'anette', 'anna', 'beatriz', 'carolina',
    'cristiana', 'daniela', 'flora', 'houda', 'ines', 'joana', 'lara',
    'leonor', 'lorena', 'maria', 'mariana', 'matilde', 'patricia', 'rita',
    'sharon', 'sofia', 'thalia', 'uliana'
  ]);

  var MALE_NAMES = new Set([
    'afonso', 'alexandre', 'andrei', 'andre', 'artem', 'carlos', 'celso',
    'daniel', 'diogo', 'duarte', 'edmund', 'eduardo', 'efe', 'felipe',
    'fidel', 'francisco', 'gabriel', 'guilherme', 'henrique', 'hugo',
    'irineu', 'jose', 'jorge', 'licinio', 'luis', 'mahdi', 'martim',
    'mikaeel', 'miguel', 'nuno', 'pavlo', 'pedro', 'rafael', 'renato',
    'ricardo', 'rihan', 'rongkai', 'rui', 'sandro', 'vitor', 'youssef'
  ]);

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();
  }

  function itemX(item) {
    if (item && item.transform && Number.isFinite(item.transform[4])) {
      return item.transform[4];
    }
    return Number(item && (item.x || item.x0)) || 0;
  }

  function itemY(item) {
    if (item && item.transform && Number.isFinite(item.transform[5])) {
      return item.transform[5];
    }
    if (Number.isFinite(Number(item && item.y))) return Number(item.y);
    if (Number.isFinite(Number(item && item.top))) return -Number(item.top);
    return 0;
  }

  function itemWidth(item) {
    if (Number.isFinite(Number(item && item.width))) return Number(item.width);
    if (Number.isFinite(Number(item && item.x1)) && Number.isFinite(Number(item && item.x0))) {
      return Number(item.x1) - Number(item.x0);
    }
    return 0;
  }

  function groupTextItemsIntoRows(items) {
    var sorted = (items || []).filter(function (item) {
      return String(item && item.str || item && item.text || '').trim();
    }).map(function (item) {
      return {
        str: String(item.str || item.text || '').trim(),
        x: itemX(item),
        y: itemY(item),
        width: itemWidth(item),
        height: Number(item.height) || 0
      };
    }).sort(function (a, b) {
      return Math.abs(b.y - a.y) > 0.5 ? b.y - a.y : a.x - b.x;
    });

    var rows = [];
    sorted.forEach(function (item) {
      var tolerance = Math.max(3.5, Math.min(6, (item.height || 9) * 0.55));
      var row = rows.find(function (candidate) {
        return Math.abs(candidate.y - item.y) <= tolerance;
      });
      if (!row) {
        row = { y: item.y, items: [] };
        rows.push(row);
      }
      row.items.push(item);
      row.y = row.items.reduce(function (sum, current) {
        return sum + current.y;
      }, 0) / row.items.length;
    });

    return rows.sort(function (a, b) {
      return b.y - a.y;
    }).map(function (row) {
      row.items.sort(function (a, b) { return a.x - b.x; });
      row.text = row.items.map(function (item) { return item.str; }).join(' ').replace(/\s+/g, ' ').trim();
      return row;
    });
  }

  function headerLabel(value) {
    var normalized = normalizeText(value);
    if (/nota\s+final|final\s+grade|final\s+mark/.test(normalized)) return 'Nota final';
    if (/classificacao\s+final|resultado\s+final/.test(normalized)) return 'Resultado final';
    if (/nota|grade|mark|classificacao|resultado|result/.test(normalized)) return 'Nota';
    if (/exame|exam/.test(normalized)) return 'Exame';
    if (/frequencia/.test(normalized)) return 'Frequencia';
    if (/oral/.test(normalized)) return 'Oral';
    if (/escrit[ao]|written/.test(normalized)) return 'Escrita';
    return '';
  }

  function detectGradeHeaders(rows) {
    var best = [];
    (rows || []).forEach(function (row) {
      var normalized = normalizeText(row.text);
      var mentionsStudent = /\b(aluno|student|matricula|numero|n\.?o)\b/.test(normalized) || /n[\u00ba\u00b0]/i.test(row.text);
      var mentionsGrade = /\b(nota|grade|mark|classificacao|resultado|result|exame|exam|frequencia|oral|escrita|written)\b/.test(normalized);
      if (!mentionsStudent || !mentionsGrade) return;

      var columns = [];
      row.items.forEach(function (item) {
        var normalizedItem = normalizeText(item.str);
        var noteCount = (normalizedItem.match(/\b(?:nota|grade|mark)\b/g) || []).length;
        if (noteCount > 1) {
          for (var noteIndex = 0; noteIndex < noteCount; noteIndex += 1) {
            columns.push({
              label: noteIndex === noteCount - 1 && /(?:nota|grade|mark)\s+final/.test(normalizedItem) ? 'Nota final' : 'Nota',
              x: item.x + (item.width * ((noteIndex + 0.5) / noteCount))
            });
          }
          return;
        }
        if (/^(final|final result|final grade)$/.test(normalizedItem) && columns.length) {
          columns[columns.length - 1].label = 'Nota final';
          return;
        }
        var label = headerLabel(item.str);
        if (label) {
          columns.push({ label: label, x: item.x + (item.width / 2) });
        }
      });

      if (!columns.length) {
        var fallbackNoteCount = (normalized.match(/\bnota\b/g) || []).length;
        for (var index = 0; index < fallbackNoteCount; index += 1) {
          columns.push({ label: index === fallbackNoteCount - 1 && /nota\s+final/.test(normalized) ? 'Nota final' : 'Nota', x: index });
        }
      }
      if (columns.length > best.length) best = columns;
    });
    return best;
  }

  function normalizeClassCode(value) {
    var compact = String(value || '').toUpperCase().replace(/[\s.-]+/g, '');
    var management = compact.match(/^(GA\d{1,2})$/);
    if (management) return management[1];
    var international = compact.match(/^GI([A-Z]?)(\d{1,2})$/);
    if (international) return 'Gi' + international[1] + international[2];
    return String(value || '').trim();
  }

  function extractClassCode(text) {
    var value = String(text || '');
    var direct = value.match(/\b(GA\s*[-.]?\s*\d{1,2}|GI\s*[-.]?\s*[A-Z]?\s*[-.]?\s*\d{1,2})\b/i);
    if (direct) return { raw: direct[0], code: normalizeClassCode(direct[0]), index: direct.index };

    var labelled = value.match(/\b(?:turma|class)\s*[:.-]?\s*([A-Z]{1,3}\d{0,2})\b/i);
    if (labelled && (/\d/.test(labelled[1]) || labelled[1].length === 1)) {
      return { raw: labelled[0], code: 'Turma ' + labelled[1].toUpperCase(), index: labelled.index };
    }
    return null;
  }

  function findStudentNumber(text) {
    var match = String(text || '').match(/(?:^|\D)(\d{5,10})(?!\d)/);
    return match ? match[1] : '';
  }

  function cleanResultToken(value) {
    return String(value || '').trim().replace(/^[\s:;|()\[\]]+|[\s:;|()\[\],.]+$/g, '');
  }

  function isResultToken(value, allowLetterGrade) {
    var token = cleanResultToken(value);
    if (!token) return false;
    var normalized = normalizeText(token).toUpperCase();
    if (STATUS_VALUES.has(normalized)) return true;
    if (/^\d{1,3}(?:[.,]\d{1,3})?%$/.test(token)) return true;
    if (/^\d{1,2}(?:[.,]\d{1,3})?$/.test(token)) {
      var numeric = Number(token.replace(',', '.'));
      return numeric >= 0 && numeric <= 20;
    }
    return Boolean(allowLetterGrade && /^[A-F][+-]?$/.test(token.toUpperCase()));
  }

  function extractResultTokens(row, studentNumber, headers) {
    var results = [];
    (row.items || []).forEach(function (item) {
      String(item.str || '').split(/\s+/).forEach(function (part) {
        var token = cleanResultToken(part);
        if (!token || token === studentNumber) return;
        if (isResultToken(token, headers.length > 0)) {
          results.push({ value: token, x: item.x + (item.width / 2) });
        }
      });
    });
    return results;
  }

  function escapeRegExp(value) {
    return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function extractInlineName(rowText, studentNumber, classInfo, results) {
    var numberIndex = rowText.indexOf(studentNumber);
    var remainder = numberIndex >= 0 ? rowText.slice(numberIndex + studentNumber.length) : rowText;
    if (classInfo) remainder = remainder.replace(classInfo.raw, ' ');
    (results || []).forEach(function (result) {
      remainder = remainder.replace(new RegExp('(?:^|\\s)' + escapeRegExp(result.value) + '(?=\\s|$)', 'i'), ' ');
    });
    remainder = remainder
      .replace(/\b(?:nota|final|grade|mark|resultado|classificacao|exame|frequencia|oral|escrita)\b/gi, ' ')
      .replace(/[|;,:()\[\]]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    if (!/[A-Za-z\u00c0-\u024f]/.test(remainder)) return '';
    if (isResultToken(remainder, true)) return '';
    return remainder;
  }

  function extractRecordsFromRows(rows, source) {
    var headers = detectGradeHeaders(rows);
    var hasGradeTable = headers.length > 0;
    var candidates = [];

    (rows || []).forEach(function (row) {
      var studentNumber = findStudentNumber(row.text);
      if (!studentNumber) return;
      var classInfo = extractClassCode(row.text);
      var results = extractResultTokens(row, studentNumber, headers);
      var inlineName = extractInlineName(row.text, studentNumber, classInfo, results);
      var useful = hasGradeTable || results.length > 0 || Boolean(classInfo) || Boolean(inlineName);
      if (!useful) return;

      candidates.push({
        num: studentNumber,
        inlineName: inlineName,
        inlineClassCode: classInfo ? classInfo.code : '',
        results: results,
        headers: headers,
        isGradeRow: hasGradeTable || results.length > 0,
        source: source && source.name || '',
        page: source && source.page || 0,
        rawText: row.text
      });
    });
    return candidates;
  }

  function inferGender(name) {
    var firstName = normalizeText(name).split(/\s+/)[0];
    if (!firstName) return '';
    if (FEMALE_NAMES.has(firstName)) return 'female';
    if (MALE_NAMES.has(firstName)) return 'male';
    return '';
  }

  function expandStatus(value, name) {
    var token = cleanResultToken(value);
    var normalized = normalizeText(token).toUpperCase();
    if (normalized === 'RE') {
      var gender = inferGender(name);
      if (gender === 'female') return 'Reprovada';
      if (gender === 'male') return 'Reprovado';
      return 'Reprovado/a';
    }
    if (normalized === 'NA' || normalized === 'N/A') return 'N/A';
    return token;
  }

  function formatDetails(record, name) {
    var results = (record.results || []).slice().sort(function (a, b) { return a.x - b.x; });
    var headers = record.headers || [];
    if (!results.length) return 'Sem resultado legivel';

    return results.map(function (result, index) {
      var label = '';
      if (headers.length === results.length) {
        label = headers[index].label;
      } else if (headers.length) {
        var nearest = headers.reduce(function (best, header) {
          var distance = Math.abs(header.x - result.x);
          return !best || distance < best.distance ? { header: header, distance: distance } : best;
        }, null);
        label = nearest && nearest.header.label;
      }
      if (!label) {
        label = results.length === 1 ? 'Nota' : (index === results.length - 1 ? 'Resultado final' : 'Resultado ' + (index + 1));
      }
      return label + ': ' + expandStatus(result.value, name);
    }).join(' | ');
  }

  function isManagementClass(classCode) {
    return /^(?:GA\d{1,2}|Gi[A-Z]?\d{1,2})$/i.test(String(classCode || '').trim());
  }

  return {
    normalizeText: normalizeText,
    groupTextItemsIntoRows: groupTextItemsIntoRows,
    detectGradeHeaders: detectGradeHeaders,
    extractRecordsFromRows: extractRecordsFromRows,
    normalizeClassCode: normalizeClassCode,
    formatDetails: formatDetails,
    inferGender: inferGender,
    isManagementClass: isManagementClass
  };
});
