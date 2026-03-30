// Income document extraction schema and function.
// Supports pay stubs, offer letters, and bank statements.

enum PayFrequency {
  Weekly      @description("Paid every week")
  BiWeekly    @description("Paid every two weeks")
  Monthly     @description("Paid once per month")
  Other       @description("Any other pay schedule (semi-monthly, quarterly, etc.)")
}

class IncomePeriod {
  start_date string @description("Start of the pay period or income period, ISO 8601 date e.g. 2024-01-01")
  end_date   string @description("End of the pay period or income period, ISO 8601 date e.g. 2024-01-31")
}

class IncomeExtraction {
  // Required fields for a successful extraction (enforced in Python, optional here for partial results)
  employer_name   string?         @description("Name of the employer or company")
  gross_income    float?          @description("Gross income amount as a numeric value, no currency symbols. e.g. 5000.00")
  pay_frequency   PayFrequency?   @description("How often the employee is paid")

  // Contextual fields
  income_period   IncomePeriod?   @description("The date range this document covers")
  employee_name   string?         @description("Name of the employee or account holder")
  document_type   string?         @description("One of: pay_stub, offer_letter, bank_statement, other")
  net_income      float?          @description("Net (take-home) income as a numeric value, if shown")
  currency        string?         @description("ISO 4217 currency code, e.g. USD, EUR, GBP")

  // Confidence signal
  confidence_notes string[]       @description("List any fields that were ambiguous, unclear, estimated, or could not be found. Empty list if everything was clear.")
}

function ExtractIncome(doc: image | pdf) -> IncomeExtraction {
  client ExtractorWithFallback
  prompt #"
    {{ _.role("system") }}
    You are a financial document analyst. Your task is to extract structured
    income data from the uploaded document (pay stub, offer letter, or bank
    statement).

    RULES:
    - Return null for any field that is NOT clearly present in the document.
      Do NOT guess or infer values that are not explicitly shown.
    - gross_income and net_income MUST be numeric values only (e.g. 5000.00).
      Never return text like "three thousand dollars" or "$5,000" — only the
      bare number.
    - For pay_frequency, determine from pay period dates or explicit labels.
      If unclear, return null rather than guessing.
    - For income_period, extract the exact date range shown on the document.
    - Populate confidence_notes with any issues: illegible text, ambiguous
      values, fields you were uncertain about, or anything noteworthy.
      Leave it as an empty list if everything was clear.

    {{ ctx.output_format }}

    {{ _.role("user") }}
    Extract the income data from this document:
    {{ doc }}
  "#
}
