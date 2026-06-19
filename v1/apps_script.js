// ============================================================
//  MAST — Webhook receptor para Google Sheets
//  Cole este código inteiro no editor do Apps Script da planilha.
//  Após salvar, crie (ou atualize) o deployment:
//    Implantações > Gerenciar implantações > Nova implantação
//    Tipo: App da Web
//    Executar como: Eu
//    Quem tem acesso: Qualquer pessoa
//
//  Propriedades do script necessárias (Configurações do projeto):
//    SPREADSHEET_ID  — ID da planilha
//    WEBHOOK_SECRET  — token secreto (mesma string que SHEETS_WEBHOOK_SECRET no GitHub)
// ============================================================

// SPREADSHEET_ID e WEBHOOK_SECRET não estão hardcoded aqui.
// Configure em: Apps Script > Configurações do projeto > Propriedades do script
var SPREADSHEET_ID = PropertiesService.getScriptProperties().getProperty("SPREADSHEET_ID");
var WEBHOOK_SECRET = PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET");
var SHEET_NAME     = "script_git";
var COLUNAS        = [
  "Titulo", "Link", "Data Publicacao", "Fonte",
  "Resumo", "Termo Buscado", "Origem", "Data Captura", "Conteudo Artigo"
];

// ------------------------------------------------------------
//  doPost — recebe os dados do Python e insere na planilha
// ------------------------------------------------------------
function doPost(e) {
  try {
    // 1. Validar presença do body
    if (!e || !e.postData || !e.postData.contents) {
      return _resposta({ status: "error", message: "postData ausente ou vazio" });
    }

    // 2. Parsear JSON
    var payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return _resposta({ status: "error", message: "JSON inválido: " + parseErr.toString() });
    }

    // 3. Validar token secreto (no body, não exposto em logs de URL)
    if (!WEBHOOK_SECRET || payload.secret !== WEBHOOK_SECRET) {
      return _resposta({ status: "error", message: "Unauthorized" });
    }

    // 4. Validar campo "rows"
    if (!payload || !Array.isArray(payload.rows)) {
      return _resposta({ status: "error", message: "Campo 'rows' ausente ou não é array" });
    }

    var rows = payload.rows;
    if (rows.length === 0) {
      return _resposta({ status: "ok", inserted: 0 });
    }

    // 5. Abrir planilha e aba
    var sheet = _getSheet();
    _garantirCabecalho(sheet);

    // 6. Normalizar linhas (garantir 8 colunas, substituir null por "")
    var normalizadas = rows.map(function(row) {
      var r = Array.isArray(row) ? row.slice() : [];
      while (r.length < COLUNAS.length) r.push("");
      return r.slice(0, COLUNAS.length).map(function(v) {
        return (v === null || v === undefined) ? "" : String(v);
      });
    });

    // 7. Inserir em batch (setValues é muito mais rápido que appendRow em loop)
    var lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, normalizadas.length, COLUNAS.length)
         .setValues(normalizadas);

    return _resposta({ status: "ok", inserted: normalizadas.length });

  } catch (err) {
    // Qualquer erro inesperado: retorna JSON em vez de página HTML de erro
    return _resposta({ status: "error", message: err.toString() });
  }
}

// ------------------------------------------------------------
//  doGet — health-check (acessível via browser)
// ------------------------------------------------------------
function doGet(e) {
  return _resposta({ status: "ok", message: "MAST Sheets Webhook ativo" });
}

// ------------------------------------------------------------
//  Helpers
// ------------------------------------------------------------
function _getSheet() {
  if (!SPREADSHEET_ID) throw new Error("SPREADSHEET_ID não configurado. Vá em Configurações do projeto > Propriedades do script.");
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  if (!ss) throw new Error("Planilha não encontrada: " + SPREADSHEET_ID);
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) throw new Error("Aba '" + SHEET_NAME + "' não encontrada na planilha.");
  return sheet;
}

function _garantirCabecalho(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, COLUNAS.length).setValues([COLUNAS]);
  }
}

function _resposta(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
