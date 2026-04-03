// W-2 Wage and Tax Statement + Earnings Statement extraction schema.
// Treats a combined W-2 / pay stub document as a single extraction target.

class TaxWithholding {
  federal_income_tax  float?  @description("Federal income tax withheld (Box 2)")
  social_security_tax float?  @description("Social security tax withheld (Box 4)")
  medicare_tax        float?  @description("Medicare tax withheld (Box 6)")
  state_income_tax    float?  @description("State income tax withheld (Box 17)")
}

class EarningsLineItem {
  description    string? @description("Earnings category, e.g. Regular Salary, Overtime, Bonus")
  hours          float?  @description("Hours worked for this line item")
  rate           float?  @description("Hourly rate for this line item")
  current_amount float?  @description("Current period amount as a numeric value")
  ytd_amount     float?  @description("Year-to-date amount as a numeric value")
}

class DeductionLineItem {
  description    string? @description("Deduction category, e.g. Federal Income Tax, 401(k) Contribution, Health Insurance")
  current_amount float?  @description("Current period deduction amount as a numeric value")
  ytd_amount     float?  @description("Year-to-date deduction amount as a numeric value")
}

class W2EarningsExtraction {
  // --- Employer ---
  employer_name    string?  @description("Name of the employer or company (Box c)")
  employer_ein     string?  @description("Employer Identification Number (Box a), e.g. 74-3928156")
  employer_address string?  @description("Full employer address including city, state, ZIP (Box c)")

  // --- Employee ---
  employee_name    string?  @description("Full name of the employee (Box e)")
  employee_ssn     string?  @description("Employee Social Security Number (Box b), e.g. 123-45-6789. Include the full SSN as shown on the document.")
  employee_address string?  @description("Full employee address including city, state, ZIP (Box e)")
  employee_id      string?  @description("Employee ID from earnings statement, e.g. EMP-20847")
  department       string?  @description("Department or division from earnings statement")

  // --- W-2 Financials ---
  wages_tips_compensation float?           @description("Wages, tips, other compensation (Box 1) as a numeric value")
  social_security_wages   float?           @description("Social security wages (Box 3) as a numeric value")
  medicare_wages          float?           @description("Medicare wages and tips (Box 5) as a numeric value")
  tax_withholding         TaxWithholding?  @description("Tax withholding amounts from all boxes")

  // --- Benefits / Codes ---
  retirement_plan  bool?    @description("Whether the Retirement plan checkbox is marked (Box 13)")
  box_12_codes     string[] @description("Box 12 entries as strings, e.g. ['D - 401(k): 4500.00']. Empty list if none.")
  control_number   string?  @description("Control number (Box d)")
  allocated_tips   float?   @description("Allocated tips (Box 8) as a numeric value")
  dependent_care   float?   @description("Dependent care benefits (Box 10) as a numeric value")

  // --- State ---
  state            string?  @description("State abbreviation (Box 15), e.g. CA")
  state_id         string?  @description("State employer ID number (Box 15)")
  state_wages      float?   @description("State wages, tips, etc. (Box 16) as a numeric value")
  state_tax        float?   @description("State income tax (Box 17) as a numeric value")

  // --- Earnings Statement ---
  pay_period       IncomePeriod?      @description("Pay period date range from the earnings statement")
  pay_date         string?            @description("Pay date in ISO 8601 format, e.g. 2025-01-17")
  pay_frequency    PayFrequency?      @description("How often the employee is paid, from the earnings statement")
  earnings         EarningsLineItem[] @description("Earnings line items from the earnings statement. Empty list if not present.")
  deductions       DeductionLineItem[] @description("Deduction line items from the earnings statement. Empty list if not present.")
  gross_pay        float?             @description("Gross pay from the earnings statement as a numeric value")
  net_pay          float?             @description("Net pay from the earnings statement as a numeric value")

  // --- Meta ---
  tax_year         int?     @description("Tax year from the W-2 form, e.g. 2025")
  document_type    string?  @description("One of: w2_earnings, w2, earnings_statement, other")
  currency         string?  @description("ISO 4217 currency code, e.g. USD")
  confidence_notes string[] @description("List any fields that were ambiguous, unclear, estimated, or could not be found. Empty list if everything was clear.")
}

function ExtractW2Earnings(doc: image | pdf) -> W2EarningsExtraction {
  client ExtractorWithFallback
  prompt #"
    {{ _.role("system") }}
    You are a tax document analyst. Your task is to extract structured data
    from a W-2 Wage and Tax Statement and/or an accompanying Earnings Statement
    (pay stub). The document may contain both forms on separate pages.

    RULES:
    - Return null for any field that is NOT clearly present in the document.
      Do NOT guess or infer values that are not explicitly shown.
    - All monetary values MUST be numeric only (e.g. 67450.00).
      Never include currency symbols, commas, or text.
    - Extract the full SSN exactly as shown (e.g. "***-**-8842" if partially masked,
      or "123-45-6789" if fully visible).
    - For box_12_codes, format each entry as "CODE_LETTER - Description: amount",
      e.g. "D - 401(k): 4500.00".
    - For earnings and deductions arrays, extract each line item separately.
    - Populate confidence_notes with any issues: illegible text, ambiguous
      values, fields you were uncertain about, or anything noteworthy.
      Leave it as an empty list if everything was clear.

    {{ ctx.output_format }}

    {{ _.role("user") }}
    Extract the W-2 and earnings statement data from this document:
    {{ doc }}
  "#
}
