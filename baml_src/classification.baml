// Document classification — routes to the correct extraction function.

enum DocumentType {
  Income       @description("Pay stubs, offer letters, bank statements — general income documents")
  W2Earnings   @description("W-2 Wage and Tax Statement, possibly combined with an Earnings Statement / pay stub")
}

function ClassifyDocument(doc: image | pdf) -> DocumentType {
  client ExtractorWithFallback
  prompt #"
    {{ _.role("system") }}
    You are a document classifier. Look at the uploaded document and determine
    its type. Respond with exactly one of the allowed categories.

    - If the document contains a W-2 form (Wage and Tax Statement), or a
      combined W-2 with an earnings/pay stub, classify it as W2Earnings.
    - For all other income-related documents (standalone pay stubs, offer
      letters, bank statements), classify it as Income.

    {{ ctx.output_format }}

    {{ _.role("user") }}
    Classify this document:
    {{ doc }}
  "#
}
