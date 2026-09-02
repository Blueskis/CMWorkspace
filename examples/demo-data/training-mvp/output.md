# Training module — CHG-041: New pricing procedure for government contracts

**Audience:** Order Management Officers (45) | **Format:** 90-min instructor-led virtual
**Prior knowledge:** ECC6 VA01/VA02 order entry, no S/4HANA exposure

## Learning objectives

By the end of this session, participants will be able to:
1. Select the correct contract tier on a government sales order in S/4HANA.
2. Verify that the system-derived price matches the contract tier before submitting.
3. Identify and correctly escalate a "no condition record found" error.
4. Explain why manual price override (their ECC6 habit) is no longer the correct action.

## Session agenda (90 min)

| Time | Segment | Format |
|---|---|---|
| 0:00–0:10 | Why this is changing (old vs. new pricing logic) | Lecture + comparison screenshot |
| 0:10–0:15 | Demo: creating a sales order end-to-end with the new flow | Live demo |
| 0:15–0:45 | Hands-on: create 3 sales orders across different contract tiers | Guided practice in sandbox |
| 0:45–0:55 | Error handling: "no condition record found" walkthrough | Live demo + guided practice |
| 0:55–1:05 | The old habit to unlearn: why NOT to manually override price | Discussion + case example |
| 1:05–1:20 | Independent practice: 2 orders, no guidance | Solo exercise |
| 1:20–1:30 | Assessment + wrap-up + where to get help post-go-live | Quiz + Q&A |

## Slide-level outline

1. **Title & objectives**
2. **Old way vs. new way** — side-by-side screenshot, ECC6 manual discount field vs.
   S/4HANA contract tier dropdown
3. **Where contract tier is selected** — annotated screenshot of the sales order screen
4. **Live demo** — placeholder slide, switch to system
5. **How to verify price is correct** — checklist: tier selected → price field populated
   → matches contract rate card
6. **Practice exercise 1 instructions**
7. **What "no condition record found" means and why it happens**
8. **Escalation path for pricing errors** — contact + ticket process
9. **Why not to override manually** — case example of an incorrect override causing a
   contract compliance issue
10. **Practice exercise 2 instructions (independent)**
11. **Knowledge check** — transition to assessment
12. **Where to get help after go-live** — job aid link, hypercare contact, office hours

## Assessment questions

1. *(Scenario)* You're creating an order for a Tier 2 government contract. Where do you
   select the contract tier, and what should happen to the price field afterward?
   *(Expected: select tier in [field], price auto-populates from condition record — do
   not key it in manually.)*

2. *(Multiple choice)* The system shows "no condition record found" for a contract order.
   What is the correct first action?
   - A. Manually enter the discount you remember from ECC6
   - B. Submit the order anyway and fix it later
   - **C. Escalate to the pricing support queue with the contract number** ✔
   - D. Ignore the error, it's cosmetic

3. *(True/False)* Manually overriding the system-derived price is an acceptable
   workaround if you're confident about the discount. *(Expected answer: False — explain
   why, referencing the contract compliance case example.)*

4. *(Short answer)* Name one way to verify a sales order's price is correct before
   submitting it.
