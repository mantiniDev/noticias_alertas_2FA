/**
 * MAST — Google Apps Script Webhook
 *
 * Como configurar (uma única vez):
 *  1. Abra a planilha → Extensões → Apps Script
 *  2. Cole este código substituindo tudo que existir
 *  3. Implante: Implantar → Nova implantação
 *       Tipo: "App da Web"
 *       Executar como: "Eu (seu e-mail)"
 *       Quem tem acesso: "Qualquer pessoa"  ← obrigatório para o Python acessar
 *  4. Copie a URL gerada (formato: https://script.google.com/macros/s/XXXXX/exec)
 *  5. Salve como secret SHEETS_WEBHOOK_URL no GitHub Actions
 *
 * Segurança opcional:
 *  - Defina TOKEN abaixo com qualquer string secreta
 *  - O Python deve enviar ?token=SUA_STRING na URL
 *  - Deixe TOKEN = "" para desabilitar a verificação
 */

var SHEET_NAME = "script_git";
var TOKEN      = "";   // ex: "mast-2026-xYz" — deixe "" para desabilitar

var CABECALHO = [
  "Titulo",
  "Link",
  "Data Publicacao",
  "Fonte",
  "Resumo",
  "Termo Buscado",
  "Origem",
  "Data Captura"
];

// ---------------------------------------------------------------------------

function doPost(e) {
  try {
    // Verificação de token (opcional)
    if (TOKEN !== "" && e.parameter.token !== TOKEN) {
      return _json({ status: "error", message: "Token inválido." }, 403);
    }

    var payload = JSON.parse(e.postData.contents);
    var rows    = payload.rows;

    if (!rows || rows.length === 0) {
      return _json({ status: "ok", inserted: 0 });
    }

    var sheet = SpreadsheetApp
      .getActiveSpreadsheet()
      .getSheetByName(SHEET_NAME);

    if (!sheet) {
      return _json({ status: "error", message: "Aba '" + SHEET_NAME + "' não encontrada." });
    }

    // Garante cabeçalho na linha 1
    _garantirCabecalho(sheet);

    // Insere todas as linhas de uma vez (muito mais rápido que appendRow em loop)
    var primeiraLinha = sheet.getLastRow() + 1;
    sheet
      .getRange(primeiraLinha, 1, rows.length, CABECALHO.length)
      .setValues(rows);

    return _json({ status: "ok", inserted: rows.length });

  } catch (err) {
    return _json({ status: "error", message: err.toString() });
  }
}

// Permite testar a URL no navegador (GET)
function doGet(e) {
  return _json({ status: "ok", message: "MAST webhook ativo." });
}

// ---------------------------------------------------------------------------

function _garantirCabecalho(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(CABECALHO);
    return;
  }
  var primeiraLinha = sheet.getRange(1, 1, 1, CABECALHO.length).getValues()[0];
  var vazia = primeiraLinha.every(function(c) { return c === ""; });
  var diferente = JSON.stringify(primeiraLinha) !== JSON.stringify(CABECALHO);
  if (vazia || diferente) {
    sheet.insertRowBefore(1);
    sheet.getRange(1, 1, 1, CABECALHO.length).setValues([CABECALHO]);
  }
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
