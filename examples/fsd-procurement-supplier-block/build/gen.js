const fs=require('fs'),path=require('path');
const D=require('docx');
const {Document,Packer,Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,WidthType,ShadingType,AlignmentType,ImageRun,PageBreak,Header,Footer,PageNumber,BorderStyle,TableOfContents,LevelFormat,PositionalTab,PositionalTabAlignment,PositionalTabLeader,convertInchesToTwip}=D;

const FIG=path.join(__dirname,'..','figures');
const CONTENT=10080; // dxa content width (Letter, 0.75in margins)
function pngSize(f){const b=fs.readFileSync(f);return{w:b.readUInt32BE(16),h:b.readUInt32BE(20)};}
let figNo=0;
function figure(file,caption){
  const p=path.join(FIG,file),{w,h}=pngSize(p);
  const W=660,H=Math.round(W*h/w);
  figNo++;
  return [
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:180,after:60},
      children:[new ImageRun({type:'png',data:fs.readFileSync(p),transformation:{width:W,height:H}})]}),
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:220},
      children:[new TextRun({text:`Figure ${figNo}: ${caption}`,italics:true,size:17,color:'44546A'})]})
  ];
}
const H1=t=>new Paragraph({text:t,heading:HeadingLevel.HEADING_1,spacing:{before:320,after:140}});
const H2=t=>new Paragraph({text:t,heading:HeadingLevel.HEADING_2,spacing:{before:240,after:110}});
const H3=t=>new Paragraph({text:t,heading:HeadingLevel.HEADING_3,spacing:{before:200,after:90}});
const P=t=>new Paragraph({spacing:{after:120},children:[new TextRun({text:t,size:20})]});
const B=t=>new Paragraph({numbering:{reference:'bul',level:0},spacing:{after:70},children:[new TextRun({text:t,size:20})]});
const N=t=>new Paragraph({numbering:{reference:'num',level:0},spacing:{after:70},children:[new TextRun({text:t,size:20})]});
const CODE=t=>new Paragraph({spacing:{after:60},shading:{type:ShadingType.CLEAR,fill:'F2F4F7'},
  children:[new TextRun({text:t,font:'Courier New',size:17})]});

function table(headers,rows,widths){
  const total=widths.reduce((a,b)=>a+b,0);
  const scale=CONTENT/total;
  const w=widths.map(x=>Math.round(x*scale));
  const cell=(txt,i,head,alt)=>new TableCell({width:{size:w[i],type:WidthType.DXA},
    shading:head?{type:ShadingType.CLEAR,fill:'1F3864'}:(alt?{type:ShadingType.CLEAR,fill:'EDF1F7'}:undefined),
    margins:{top:60,bottom:60,left:90,right:90},
    children:String(txt).split('\n').map(line=>new Paragraph({spacing:{after:0},
      children:[new TextRun({text:line,size:17,bold:!!head,color:head?'FFFFFF':'000000'})]}))});
  return new Table({
    columnWidths:w,width:{size:CONTENT,type:WidthType.DXA},
    rows:[new TableRow({tableHeader:true,children:headers.map((h,i)=>cell(h,i,true))}),
      ...rows.map((r,ri)=>new TableRow({children:r.map((c,i)=>cell(c,i,false,ri%2===1))}))]});
}
const SP=()=>new Paragraph({spacing:{after:120},children:[]});

const children=[];

/* ---------- Cover ---------- */
children.push(
 new Paragraph({spacing:{before:1400,after:120},children:[new TextRun({text:'FUNCTIONAL SPECIFICATION DOCUMENT',bold:true,size:40,color:'1F3864'})]}),
 new Paragraph({spacing:{after:60},children:[new TextRun({text:'Blocking and Unblocking of Registered Suppliers',size:30,color:'2E5C8A'})]}),
 new Paragraph({spacing:{after:400},children:[new TextRun({text:'SAP S/4HANA 2023  |  Procurement (MM)  |  RICEFW ID: MM-WA-014',size:22,color:'595959'})]}),
 table(['Attribute','Value'],[
  ['Document title','FSD - Blocking / Unblocking of Registered Suppliers'],
  ['RICEFW ID','MM-WA-014'],
  ['RICEFW type','Workflow + Application (W / A) with Report and Enhancement components'],
  ['Process area','Source to Pay - Supplier Master Data Governance'],
  ['SAP solution','SAP S/4HANA 2023 (On-Premise), SAP Fiori 3, SAP Business Workflow'],
  ['Development objects','ZMM_SUPPLIER_BLOCK, ZMM_SUPBLK_MASS, ZCL_SUPPLIER_BLOCK_MGR, WS_ZSUPBLK'],
  ['Complexity','High'],
  ['Author','J. Smith, Procurement Functional Lead'],
  ['Version / Status','1.0 / Released for Build'],
  ['Date','21 August 2026'],
 ],[2600,7480]),
 new Paragraph({children:[new PageBreak()]}),
 new Paragraph({text:'Table of Contents',heading:HeadingLevel.HEADING_1,spacing:{after:160}}),
 new TableOfContents('Contents',{hyperlink:true,headingStyleRange:'1-3'}),
 new Paragraph({children:[new PageBreak()]})
);

/* ---------- Document control ---------- */
children.push(H1('1. Document Control'),H2('1.1 Version History'),
 table(['Version','Date','Author','Description of Change'],[
  ['0.1','24.06.2026','J. Smith','Initial draft after process workshop PW-14'],
  ['0.2','09.07.2026','J. Smith','Added mass processing mode and reason code catalogue'],
  ['0.3','28.07.2026','R. Kumar','Technical review; BAPI selection and lock strategy added'],
  ['0.9','11.08.2026','J. Smith','Compliance review comments incorporated (segregation of duties)'],
  ['1.0','21.08.2026','J. Smith','Released for build; screen layouts and message class finalised'],
 ],[900,1200,1700,6280]),
 H2('1.2 Approvals'),
 table(['Role','Name','Responsibility','Approval Date'],[
  ['Process Owner - Procurement','M. Okafor','Business content and process fit','18.08.2026'],
  ['Compliance Officer','A. Pereira','Control design, segregation of duties','19.08.2026'],
  ['Finance Master Data Lead','L. Trevino','Company code block impact on AP','19.08.2026'],
  ['Solution Architect','R. Kumar','Technical feasibility and design standards','20.08.2026'],
  ['Programme Manager','S. Bianchi','Scope, budget and release assignment','21.08.2026'],
 ],[2600,1500,4380,1600]),
 H2('1.3 Related Documents'),
 table(['Reference','Document','Owner'],[
  ['BPD-P2P-04','Business Process Design - Supplier Lifecycle Management','Procurement'],
  ['BRD-0233','Business Requirement - Sanctions and Quality Blocking','Compliance'],
  ['TSD-MM-WA-014','Technical Specification (to be written from this FSD)','Development'],
  ['SEC-ROLE-MM','Authorisation Concept - Materials Management','Security'],
  ['TST-P2P-11','Test Script - Supplier Block and Unblock','Test Management'],
 ],[1800,6180,2100])
);

/* ---------- 2 Business background ---------- */
children.push(H1('2. Business Background'),
 P('The organisation maintains approximately 41,000 registered suppliers across five company codes and three purchasing organisations. Suppliers enter the master data through a governed onboarding process, but no equivalent governed process exists for suspending a supplier once it is registered. Today a block is applied by a master data administrator directly in transaction BP or XK05, on the basis of an e-mail request, with no enforced reason code, no validity period, no approval, and no consolidated audit trail.'),
 P('This has produced four recurring problems, all of which were confirmed during the FY2025 internal audit (finding IA-2025-17, rated High):'),
 B('Inconsistent scope. Administrators apply the block at whichever level they happen to open first - central, company code or purchasing organisation. In a sample of 60 blocks, 22 were applied at only one level, leaving the supplier transactable through another route. In four cases purchase orders were raised against a supplier that the business believed to be blocked.'),
 B('No reason traceability. The block indicator carries no reason. When a supplier queries its status, procurement cannot state why the block exists without searching e-mail archives. Average time to answer such a query is currently 3.5 working days.'),
 B('No time limit. 61% of currently blocked suppliers have been blocked for more than 18 months with no recorded review. Some are blocked for reasons that have long been remediated, which unnecessarily narrows the supply base and weakens negotiating position.'),
 B('No segregation of duties. The same administrator who raises the request can execute it. Compliance requires that a block applied for sanctions or fraud reasons is approved independently of the requester.'),
 P('In parallel, regulatory obligation has increased. Sanctions screening results now arrive daily from a third-party service and must be actioned within 24 hours of receipt. The current manual route cannot meet that service level: measured average turnaround from screening hit to effective block is 4.2 days, and each block is executed one supplier at a time.'),
 P('The business therefore requires a governed, auditable and partly automated capability to block and unblock registered suppliers, covering both single-supplier requests raised by procurement and mass actions triggered by compliance screening files.'),
 H2('2.1 Business Drivers and Expected Benefits'),
 table(['Driver','Current State','Target State','Benefit'],[
  ['Regulatory compliance','4.2 days average from sanctions hit to block','Within 24 hours, evidenced','Removes audit finding IA-2025-17; avoids sanctions exposure'],
  ['Control and segregation of duties','Requester executes own request','Two-step approval, requester excluded as approver','SOX-relevant control, testable'],
  ['Auditability','No reason, no history','Reason code, validity, attachment, change document','Query answered from one screen'],
  ['Supply base health','61% of blocks never reviewed','Validity date drives expiry and review worklist','Blocked base expected to fall by ~30% in year one'],
  ['Efficiency','Manual, one supplier at a time','Mass mode, up to 5,000 suppliers per run','Estimated 0.6 FTE released in master data team'],
 ],[1900,2400,2500,3280]),
 H2('2.2 Business Rules'),
 table(['Rule ID','Business Rule'],[
  ['BR-01','A registered supplier may only be blocked through the governed request process. Direct maintenance of the block indicators in BP / XK05 is withdrawn from all end-user roles.'],
  ['BR-02','Every block and every unblock must carry a reason code from the approved catalogue (Appendix A) and a free-text justification of at least 20 characters.'],
  ['BR-03','Blocks raised under a compliance reason (BC*) require approval by a Compliance Officer. Blocks raised under quality (BQ*) or commercial (BF*) reasons require approval by the responsible Category Manager.'],
  ['BR-04','The requester of a block or unblock can never be an approver of the same request, irrespective of role assignment.'],
  ['BR-05','A block with reason code group BC* (sanctions, adverse media, debarment) is always applied centrally and has no valid-to date. It can only be lifted by an unblock request approved by Compliance.'],
  ['BR-06','A supplier flagged for deletion may not be blocked; the deletion flag already prevents transaction.'],
  ['BR-07','Blocking does not delete or reverse existing purchasing documents. Open documents remain visible but are prevented from further release, goods receipt and invoice payment.'],
  ['BR-08','Where the supplier is the sole source for an active source list entry, the request may still proceed but the warning must be acknowledged and is recorded in the audit log.'],
  ['BR-09','A block whose valid-to date is reached is released automatically by the nightly job, and the responsible category manager is notified seven calendar days in advance.'],
  ['BR-10','All block and unblock events are retained for ten years to satisfy the record retention policy.'],
 ],[1100,8980])
);

/* ---------- 3 scope ---------- */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('3. Functional Description and Scope'),
 H2('3.1 Functional Description'),
 P('The solution introduces a single governed entry point for suspending and reinstating registered suppliers. A requester selects a supplier, states the scope of the block, chooses a reason code and validity period, and attaches supporting evidence. The application validates the request against master data, authorisation and open document checks, then routes it through a two-step approval. On final approval the application sets the corresponding block indicators on the business partner and vendor views, writes a full audit record, and publishes the change to downstream consumers. Unblocking uses the same mechanism with release reason codes, clearing the indicators that the original request set.'),
 P('A second, non-dialog mode supports mass processing. A pre-approved input file - typically the daily sanctions screening result - is processed in the background by report ZMM_SUPBLK_MASS, which applies the identical validation and update logic per supplier and produces a consolidated ALV and application log. The approval evidence in this mode is held against the file rather than the individual supplier.'),
 H2('3.2 In Scope'),
 table(['#','In Scope Item','Detail'],[
  ['1','Single-supplier block request','Fiori application, dialog, with impact preview and attachment'],
  ['2','Single-supplier unblock request','Same application, action = Unblock, release reason codes RL*'],
  ['3','Mass block / unblock','Report ZMM_SUPBLK_MASS, foreground test run and background update run'],
  ['4','Two-step approval workflow','SAP Flexible Workflow WS_ZSUPBLK, My Inbox, 48-hour escalation'],
  ['5','Block scopes','Central (LFA1), company code (LFB1), purchasing organisation (LFM1)'],
  ['6','Reason code catalogue','Custom table ZMM_SUPBLK_RSN with maintenance view V_ZSUPBLK_RSN'],
  ['7','Validity handling','Valid-from / valid-to, automatic expiry job ZMM_SUPBLK_EXPIRE, 7-day pre-notification'],
  ['8','Audit trail','Custom tables ZMM_SUPBLK_HDR / ZMM_SUPBLK_LOG, BP change documents, SLG1 log'],
  ['9','Reporting','Blocked Supplier Report (CDS view ZC_BLOCKED_SUPPLIER) with Fiori list page'],
  ['10','Downstream notification','BP change event published to SAP BTP Event Mesh for Ariba and SAC'],
  ['11','Authorisation','New object Z_SUPBLK controlling action, purchasing org, company code and reason group'],
  ['12','Enhancement','BP screen made display-only for block fields via BDT event; ME21N / MIRO messages hardened'],
 ],[600,3100,6380]),
 H2('3.3 Out of Scope'),
 B('Blocking of one-time vendors and employee vendors (account groups CPD and ZEMP). These are handled by the existing employee master process.'),
 B('Customer-side blocking. The equivalent control for customer master data is covered by a separate RICEFW (SD-WA-009).'),
 B('Deletion or archiving of supplier master records. The deletion flag remains a master data function outside this solution.'),
 B('Automated sanctions screening itself. This solution consumes screening results; it does not perform matching or scoring.'),
 B('Retroactive blocking of already posted invoices. Documents already posted are not reversed, and existing payment proposals are not modified by this solution.'),
 B('Migration of historical block reasons. Existing blocks are carried forward with reason code BL99 "Legacy block - reason not recorded" and must be reviewed manually within six months of go-live.'),
 H2('3.4 Assumptions'),
 table(['ID','Assumption','Impact if Invalid'],[
  ['A-01','Business partner is the single point of entry for supplier master data (CVI active and synchronised).','Direct vendor updates would bypass the control; a second update path would be required.'],
  ['A-02','SAP Flexible Workflow is active and My Inbox is deployed to all approver roles.','Approval would fall back to classic workflow, adding an estimated 12 person-days.'],
  ['A-03','Category Manager and Compliance Officer are maintained as agents in the workflow responsibility rules.','Requests would route to a fallback agent group, weakening the control.'],
  ['A-04','The daily screening file arrives in a fixed CSV layout on the interface directory by 05:00 local time.','Mass mode input handling would need a mapping layer.'],
  ['A-05','No more than 5,000 suppliers are processed in a single mass run.','Package size and runtime assumptions in section 9 would need to be revisited.'],
  ['A-06','Reason code catalogue is owned by Compliance and maintained in production through a transport-free maintenance view.','Changes would require a transport and a release cycle.'],
 ],[600,4700,4780]),
 H2('3.5 Dependencies'),
 table(['ID','Dependency','Owner','Needed By'],[
  ['D-01','Authorisation object Z_SUPBLK built and roles updated','Security','Unit test start'],
  ['D-02','Removal of block field maintenance from existing BP roles','Security','Go-live'],
  ['D-03','Reason code catalogue signed off by Compliance','Compliance','Build start'],
  ['D-04','Event Mesh topic supplier/block/v1 provisioned','Integration','Integration test'],
  ['D-05','Interface directory and file handling for screening file','Basis','Integration test'],
  ['D-06','Legacy block data cleansed and loaded with reason BL99','Data Migration','Cutover'],
 ],[600,5100,2180,2200])
);

/* ---------- 4 process flow ---------- */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('4. Process Flow'),
 P('The end-to-end process is shown below. Swimlanes separate the requester, the custom application, the approver, the S/4HANA core master data update, and the downstream consumers. The unblock process is identical in structure; only the reason code group and the direction of the indicator update differ.'),
 ...figure('f02_flow.png','End-to-end process flow - supplier block and unblock'),
 H2('4.1 Process Step Description'),
 table(['Step','Actor','Description','System Object'],[
  ['1','Requester','Selects the supplier and the block scope (central, company code, purchasing organisation). Supplier value help excludes account groups CPD and ZEMP.','ZMM_SUPPLIER_BLOCK'],
  ['2','Requester','Enters reason code, validity dates, justification text and attaches evidence. Impact preview is refreshed automatically.','ZMM_SUPPLIER_BLOCK'],
  ['3','System','Runs the validation set in section 7.4: master data status, authorisation, duplicate request, open document check, sole-source check.','ZCL_SUPPLIER_BLOCK_MGR->VALIDATE'],
  ['3a','Requester','On error, corrects the entry and resubmits. Warnings may be acknowledged and the request continues.','Message class ZSUPBLK'],
  ['4','System','Persists the request with status IN APPROVAL and starts the workflow. Request number is drawn from number range ZSUPBLK.','ZMM_SUPBLK_HDR'],
  ['5','Approver','Reviews the request in My Inbox including spend, open document value and alternative sources, then approves or rejects with a decision note.','WS_ZSUPBLK'],
  ['5a','System','On rejection sets status REJECTED and notifies the requester by e-mail. No master data change occurs.','WS_ZSUPBLK'],
  ['6','System','On final approval sets the block indicators in the relevant tables through BAPI calls in a single LUW, with the business partner locked for the duration.','BAPI_BUPA_CENTRAL_CHANGE / VENDOR_UPDATE'],
  ['7','System','Writes the audit record, the application log and the change document. Commits the LUW.','ZMM_SUPBLK_LOG / SLG1'],
  ['8','System','Publishes the block event to SAP BTP Event Mesh for consumption by Ariba Buying and SAC compliance reporting.','Topic supplier/block/v1'],
 ],[600,1200,6100,2180]),
 H2('4.2 Status Model'),
 table(['Status','Meaning','Permitted Next Status','Set By'],[
  ['DRAFT','Saved but not submitted. Visible only to the requester.','IN APPROVAL, DELETED','Requester'],
  ['IN APPROVAL','Submitted, workflow running.','APPROVED, REJECTED, WITHDRAWN','System'],
  ['APPROVED','Both approval steps complete; update pending or in progress.','ACTIVE, FAILED','Workflow'],
  ['ACTIVE','Block indicators set in master data. This is the effective state.','EXPIRED, RELEASED','System'],
  ['REJECTED','Declined by an approver. Terminal.','-','Approver'],
  ['WITHDRAWN','Cancelled by the requester before final approval. Terminal.','-','Requester'],
  ['EXPIRED','Valid-to date reached; indicators cleared by the nightly job. Terminal.','-','Job'],
  ['RELEASED','Cleared by an approved unblock request. Terminal.','-','System'],
  ['FAILED','Master data update failed and was rolled back. Requires re-processing.','ACTIVE','System'],
 ],[1400,4200,2500,1980])
);

/* ---------- 5 application system ---------- */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('5. Application System'),
 P('The solution is built entirely within SAP S/4HANA, with integration points to the screening provider on the inbound side and to Ariba and analytics on the outbound side. No custom persistence exists outside S/4HANA.'),
 ...figure('f01_landscape.png','Application system landscape and integration points'),
 H2('5.1 Systems and Clients'),
 table(['System','SID / Client','Role','Notes'],[
  ['SAP S/4HANA Development','S4D / 100','Build and unit test','All custom objects created here'],
  ['SAP S/4HANA Quality','S4Q / 200','Integration and UAT','Refreshed from production 3 months before go-live'],
  ['SAP S/4HANA Production','S4P / 100','Live operation','Change through normal transport route only'],
  ['SAP BTP Integration Suite','CPI-PRD','Screening file inbound, event routing','Existing tenant, new iFlow required'],
  ['SAP Ariba Buying','Ariba-PRD','Consumes block status to suppress supplier in guided buying','Near real-time via event'],
  ['SAP Analytics Cloud','SAC-PRD','Compliance dashboard on blocked base','Daily extract from CDS view'],
 ],[2400,1500,3300,2880]),
 H2('5.2 Development Objects'),
 table(['Object','Type','Description'],[
  ['ZMM_SUPPLIER_BLOCK','Fiori application (SAPUI5 freestyle)','Create, display and maintain block / unblock requests'],
  ['ZMM_SUPBLK_SRV','OData V2 service','Backend service for the Fiori application'],
  ['ZMM_SUPBLK_MASS','ABAP report','Mass block / unblock with test run and background execution'],
  ['ZMM_SUPBLK_EXPIRE','ABAP report','Nightly expiry of blocks whose valid-to date has passed'],
  ['ZCL_SUPPLIER_BLOCK_MGR','ABAP class','Central validation, update and logging logic; single point of change'],
  ['WS_ZSUPBLK','Flexible Workflow scenario','Two-step approval with escalation'],
  ['ZMM_SUPBLK_HDR','Transparent table','Request header, one row per request'],
  ['ZMM_SUPBLK_LOG','Transparent table','Audit log, one row per indicator change'],
  ['ZMM_SUPBLK_RSN','Customising table','Reason code catalogue with maintenance view V_ZSUPBLK_RSN'],
  ['ZC_BLOCKED_SUPPLIER','CDS view','Consumption view for the blocked supplier report and SAC'],
  ['ZSUPBLK','Message class','All messages raised by the solution'],
  ['Z_SUPBLK','Authorisation object','Fields ACTVT, EKORG, BUKRS, ZRSNGRP'],
  ['ZSUPBLK_BDT','BDT event enhancement','Sets block fields to display-only in transaction BP'],
 ],[2400,2600,5080]),
 H2('5.3 Entry Points'),
 P('All user entry runs through the SAP Fiori launchpad space "Procurement", page "Supplier Governance". Classic GUI access is retained only for the mass report and the application log, and is restricted to the master data support role.'),
 ...figure('f03_launchpad.png','SAP Fiori launchpad - Supplier Block Management tile group')
);

/* ---------- 6 data model ---------- */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('6. Data Model'),
 H2('6.1 Standard Fields Updated'),
 P('The solution sets and clears the following standard indicators. No other standard field is written.'),
 table(['Table','Field','Description','Set When','Cleared When'],[
  ['LFA1','SPERR','Central posting block','Scope = Central','Unblock or expiry'],
  ['LFA1','SPERM','Central purchasing block','Scope = Central','Unblock or expiry'],
  ['LFA1','SPERZ','Central payment block','Reason group BC* or BF*','Unblock only'],
  ['LFB1','SPERR','Posting block for company code','Scope = Company Code','Unblock or expiry'],
  ['LFM1','SPERM','Purchasing block for purchasing organisation','Scope = Purchasing Org','Unblock or expiry'],
  ['LFM1','SPERR_FKT','Function that is blocked','Always, from field Blocked Functions','Unblock or expiry'],
  ['BUT000','XBLCK','Business partner central block','Scope = Central','Unblock or expiry'],
 ],[900,1100,3400,2400,2280]),
 H2('6.2 Custom Table ZMM_SUPBLK_HDR'),
 table(['Field','Key','Data Element','Description'],[
  ['MANDT','X','MANDT','Client'],
  ['REQNO','X','ZE_SUPBLK_REQNO','Request number, number range ZSUPBLK, 10 digits'],
  ['LIFNR','','LIFNR','Supplier account number'],
  ['PARTNER','','BU_PARTNER','Business partner number'],
  ['ACTION','','ZE_SUPBLK_ACTION','B = Block, U = Unblock'],
  ['SCOPE','','ZE_SUPBLK_SCOPE','C = Central, B = Company Code, P = Purchasing Org'],
  ['BUKRS','','BUKRS','Company code, filled when SCOPE = B'],
  ['EKORG','','EKORG','Purchasing organisation, filled when SCOPE = P'],
  ['RSNCD','','ZE_SUPBLK_RSN','Reason code, check table ZMM_SUPBLK_RSN'],
  ['FUNCT','','ZE_SUPBLK_FUNCT','Blocked function, A / B / C'],
  ['DATFROM','','DATS','Valid from'],
  ['DATTO','','DATS','Valid to, initial means unlimited'],
  ['JUSTIF','','ZE_SUPBLK_TEXT','Justification, 255 characters, mandatory minimum 20'],
  ['STATUS','','ZE_SUPBLK_STAT','Status per section 4.2'],
  ['WI_ID','','SWW_WIID','Workflow work item ID'],
  ['ATTACH_ID','','SDOK_DOCID','GOS attachment reference'],
  ['ERNAM / ERDAT / ERZET','','SYUNAME / DATS / TIMS','Created by, date, time'],
  ['AENAM / AEDAT / AEZET','','SYUNAME / DATS / TIMS','Last changed by, date, time'],
 ],[2000,600,2200,5280]),
 H2('6.3 Custom Table ZMM_SUPBLK_LOG'),
 P('One row is written for every indicator that is set or cleared, giving a field-level audit independent of the request header. The table is never updated after insert.'),
 table(['Field','Key','Description'],[
  ['MANDT / LOGID','X','Client and log GUID'],
  ['REQNO','','Originating request number, or MASS-<run id> for mass processing'],
  ['LIFNR / PARTNER','','Supplier and business partner'],
  ['TABNAME / FIELDNAME','','Table and field changed, for example LFA1 / SPERM'],
  ['ORG_KEY','','Company code or purchasing organisation, blank for central'],
  ['VALUE_OLD / VALUE_NEW','','Indicator before and after the change'],
  ['RSNCD','','Reason code in force at the time of the change'],
  ['CHANGED_BY / TIMESTAMP','','Executing user and UTC timestamp'],
  ['APPROVER_1 / APPROVER_2','','Users who approved the originating request'],
 ],[2600,600,6880])
);

/* ---------- 7 program flow / layout ---------- */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('7. Program Flow and Layout'),
 H2('7.1 Application Layout - Request Worklist'),
 P('The worklist is the default entry point. It is a Fiori list report over CDS view ZC_SUPBLK_REQUEST with filters on supplier, status, reason code and creation date. Rows are colour-coded by status and the user may create, copy or withdraw requests from the toolbar. Only requests the user is authorised to see under object Z_SUPBLK are returned.'),
 ...figure('f06_worklist.png','Manage Supplier Block Requests - worklist with filter bar'),
 table(['Element','Type','Behaviour'],[
  ['Supplier','Filter, value help','Search help ZSH_SUPBLK_LIFNR; excludes account groups CPD and ZEMP'],
  ['Status','Filter, dropdown','Multi-select from the status model in section 4.2; defaults to In Approval'],
  ['Reason','Filter, dropdown','Reads ZMM_SUPBLK_RSN, restricted to reason groups the user may see'],
  ['Created On','Filter, date range','Defaults to the first day of the current month'],
  ['Create','Toolbar button','Opens the request detail screen in create mode; requires Z_SUPBLK ACTVT 01'],
  ['Copy','Toolbar button','Copies the selected request excluding attachment and approval history'],
  ['Withdraw','Toolbar button','Active only for own requests in status IN APPROVAL; cancels the workflow'],
  ['Export','Toolbar button','Downloads the current result set as XLSX'],
 ],[1700,1700,6680]),
 H2('7.2 Application Layout - Request Detail'),
 P('The detail screen carries the block attributes, a live impact preview and the approval history. The impact preview is recalculated whenever supplier or scope changes and is read-only. Mandatory fields are marked with an asterisk and are enforced on submit, not on field exit.'),
 ...figure('f07_detail.png','Create Block Request - detail screen with impact preview and approval history'),
 H3('7.2.1 Field Specification'),
 table(['Field','M/O','Type / Length','Default','Rules'],[
  ['Supplier','M','LIFNR, 10','From worklist selection','Must exist, must not be flagged for deletion (BR-06), account group in ZVEN / ZINT'],
  ['Action','M','CHAR 1','B (Block)','B or U; U only permitted when an ACTIVE block exists for the same scope'],
  ['Block Scope','M','CHAR 1','C (Central)','Forced to C when reason group is BC* (BR-05)'],
  ['Company Code','C','BUKRS, 4','User default','Mandatory and only visible when scope = B; checked against Z_SUPBLK field BUKRS'],
  ['Purchasing Org.','C','EKORG, 4','User default','Mandatory and only visible when scope = P; checked against Z_SUPBLK field EKORG'],
  ['Blocked Functions','M','CHAR 1','A','A = all, B = purchasing only, C = posting only. Forced to A for reason group BC*'],
  ['Reason Code','M','CHAR 4','-','F4 from ZMM_SUPBLK_RSN filtered by action; block codes for B, RL* codes for U'],
  ['Valid From','M','DATS','Today','Not earlier than today; not later than today + 90 days'],
  ['Valid To','C','DATS','-','Must be later than Valid From (ZSUPBLK 034). Must be initial for reason group BC*'],
  ['Justification','M','CHAR 255','-','Minimum 20 characters; free text is written to the audit log verbatim'],
  ['Attachment','C','GOS','-','Mandatory for reason groups BC* and BQ*; PDF, MSG or XLSX up to 10 MB'],
 ],[1600,600,1500,1600,4780]),
 H3('7.2.2 Impact Preview Logic'),
 P('The impact preview is informational and never blocks submission on its own. Counts are read at request time and again immediately before the master data update; a material change between the two triggers warning ZSUPBLK 011 for the approver.'),
 table(['Preview Row','Source','Selection'],[
  ['Open purchase requisitions','EBAN','LIFNR = supplier, LOEKZ = space, EBAKZ = space'],
  ['Open purchase orders','EKKO / EKPO','LIFNR = supplier, LOEKZ = space, ELIKZ = space, document type not RV'],
  ['Open scheduling agreements','EKKO','BSTYP = L, LIFNR = supplier, valid-to not passed'],
  ['Open invoices','RBKP','LIFNR = supplier, RBSTAT in (A, B), reversal indicator initial'],
  ['Source list / quota entries','EORD / QUAN','LIFNR = supplier, valid period covering today'],
 ],[2600,1800,5680])
);

/* 7.3 workflow */
children.push(new Paragraph({children:[new PageBreak()]}),
 H2('7.3 Approval Workflow'),
 P('Approval uses SAP Flexible Workflow scenario WS_ZSUPBLK with two sequential steps. Step one is the responsible Category Manager derived from the supplier purchasing organisation and the dominant material group of the last twelve months of spend. Step two is a Compliance Officer, taken from the agent group derived from the reason code group. Both steps exclude the requester by rule (BR-04). Where the derived agent is also the requester, the step routes to the deputy maintained in the responsibility rule.'),
 ...figure('f08_inbox.png','My Inbox - approval task with decision context and decision note'),
 table(['Attribute','Value'],[
  ['Scenario','WS_ZSUPBLK'],
  ['Trigger','Business event ZMM_SUPBLK_REQUEST.CREATED raised on submit'],
  ['Step 1 agent','Responsibility rule ZRR_SUPBLK_CATMGR (purchasing org + material group)'],
  ['Step 2 agent','Responsibility rule ZRR_SUPBLK_COMPL (reason code group)'],
  ['Skip conditions','Step 1 is skipped for reason group BC* where speed of block is the priority; step 2 is skipped for BF* reasons where the block value is below EUR 50,000'],
  ['Deadline','Requested end 24 hours for BC*, 48 hours for all other reason groups'],
  ['Escalation','On deadline breach the work item is forwarded to Head of Procurement and an e-mail is sent to the requester'],
  ['Rejection','Terminates the workflow, sets status REJECTED and notifies the requester with the decision note'],
  ['Withdrawal','Requester withdrawal raises event CANCELLED which terminates open work items'],
 ],[2200,7880]),
 H2('7.4 Validation and Message Handling'),
 P('All validations are implemented in ZCL_SUPPLIER_BLOCK_MGR so that the Fiori application, the mass report and the expiry job behave identically. Errors prevent submission; warnings can be acknowledged, and the acknowledgement is written to the audit log with the acknowledging user.'),
 ...figure('f10_errors.png','Validation messages and message class ZSUPBLK'),
 table(['Check','Message','Type','Condition'],[
  ['Master data status','ZSUPBLK 022','E','LFA1-LOEVM or BUT000-XDELE is set'],
  ['Account group','ZSUPBLK 024','E','Account group is CPD or ZEMP'],
  ['Reason code','ZSUPBLK 031','E','Reason code not found in ZMM_SUPBLK_RSN or not valid for the chosen action'],
  ['Validity','ZSUPBLK 034','E','Valid to is earlier than or equal to valid from'],
  ['Validity','ZSUPBLK 035','E','Valid from is more than 90 days in the future'],
  ['Authorisation','ZSUPBLK 041','E','Z_SUPBLK check fails for ACTVT, EKORG, BUKRS or reason group'],
  ['Segregation of duties','ZSUPBLK 043','E','Approver equals requester and no deputy is maintained'],
  ['Duplicate','ZSUPBLK 045','E','An open request already exists for the same supplier and scope'],
  ['Unblock precondition','ZSUPBLK 047','E','Action is U but no ACTIVE block exists for the supplier and scope'],
  ['Justification','ZSUPBLK 049','E','Justification is shorter than 20 characters'],
  ['Attachment','ZSUPBLK 051','E','Attachment missing for reason group BC* or BQ*'],
  ['Open documents','ZSUPBLK 011','W','One or more open purchasing documents exist'],
  ['Existing block','ZSUPBLK 013','W','A block already exists at a different level; scope will be extended'],
  ['Sole source','ZSUPBLK 016','W','Supplier is the only entry in an active source list for a material'],
  ['Spend threshold','ZSUPBLK 018','W','Spend in the last twelve months exceeds EUR 1,000,000'],
  ['Update failure','ZSUPBLK 052','A','BAPI returned an error; the LUW is rolled back and status set to FAILED'],
 ],[2100,1400,700,5880])
);

/* 7.5 mass */
children.push(new Paragraph({children:[new PageBreak()]}),
 H2('7.5 Mass Processing - Selection Screen'),
 P('Report ZMM_SUPBLK_MASS supports both a foreground test run and a scheduled background update run. The test run performs every validation and produces the full result list without touching the database, and is mandatory before any productive mass run.'),
 ...figure('f05_selscreen.png','ZMM_SUPBLK_MASS - selection screen'),
 table(['Parameter','Technical Name','Type','Rules'],[
  ['Supplier','S_LIFNR','SELECT-OPTION','At least one of supplier, company code or account group must be filled'],
  ['Company Code','S_BUKRS','SELECT-OPTION','Checked against Z_SUPBLK field BUKRS'],
  ['Purchasing Organisation','S_EKORG','SELECT-OPTION','Checked against Z_SUPBLK field EKORG'],
  ['Supplier Account Group','S_KTOKK','SELECT-OPTION','CPD and ZEMP are excluded and cannot be entered'],
  ['Block / Unblock','P_BLOCK / P_UNBLK','RADIOBUTTON','Mutually exclusive, block is the default'],
  ['Block Scope','P_SCOPE','PARAMETER, listbox','C / B / P, consistent with the organisational selections'],
  ['Reason Code','P_RSNCD','PARAMETER','Mandatory, F4 from ZMM_SUPBLK_RSN'],
  ['Valid From / To','P_DATFR / P_DATTO','PARAMETER','Same rules as the dialog application'],
  ['Approval Reference','P_APPREF','PARAMETER','Mandatory; the compliance reference under which the file was approved'],
  ['Test Run','P_TEST','CHECKBOX','Default X; must be run at least once before the update run'],
  ['Check Open Documents','P_CHKDOC','CHECKBOX','Default X; produces warnings only'],
  ['Ignore Warnings','P_IGNW','CHECKBOX','Default blank; requires Z_SUPBLK ACTVT 21'],
  ['Write Application Log','P_LOG','CHECKBOX','Default X and not modifiable in the update run'],
  ['Package Size','P_PACK','PARAMETER','Default 500, range 100 to 2,000; controls COMMIT frequency'],
  ['E-mail Recipient','P_EMAIL','PARAMETER','Result log is sent as PDF on completion'],
 ],[2100,1900,1600,4480]),
 H2('7.6 Program Flow - Mass Report'),
 N('Read and validate the selection screen; issue error if neither supplier nor organisational selection is filled.'),
 N('Authority check on Z_SUPBLK for ACTVT (02 block, 03 unblock, 21 ignore warnings) against each purchasing organisation and company code in the selection.'),
 N('Select candidate suppliers from LFA1 joined to LFB1 and LFM1 according to the chosen scope, excluding deletion-flagged records and excluded account groups.'),
 N('Open the application log (object ZSUPBLK, sub-object BLOCK or UNBLOCK, external ID MASS-<date>-<counter>).'),
 N('Loop over the candidates in packages of P_PACK. For each supplier call ZCL_SUPPLIER_BLOCK_MGR->VALIDATE and collect the messages.'),
 N('Where validation returns an error, mark the supplier as failed and continue with the next; a single failure never terminates the run.'),
 N('In test mode, record the intended change and skip the update. In update mode, enqueue the business partner (ENQUEUE_EZBUPA), call the update method, and dequeue.'),
 N('After each package, COMMIT WORK AND WAIT and write the accumulated log entries to ZMM_SUPBLK_LOG.'),
 N('On completion, save the application log, display the ALV result and send the PDF to the e-mail recipient.'),
 N('Set the return code: 0 if all suppliers succeeded, 4 if warnings occurred, 8 if any supplier failed. The return code is evaluated by the job chain.'),
 SP(),
 P('Pseudocode for the core loop:'),
 CODE('LOOP AT lt_supplier ASSIGNING <ls_sup>.'),
 CODE('  lo_mgr->validate( EXPORTING is_request = ls_req  IMPORTING et_msg = lt_msg ).'),
 CODE('  IF line_exists( lt_msg[ msgty = \'E\' ] ) OR line_exists( lt_msg[ msgty = \'A\' ] ).'),
 CODE('    APPEND VALUE #( sup = <ls_sup>-lifnr  icon = c_red  msg = lt_msg ) TO lt_out.'),
 CODE('    CONTINUE.'),
 CODE('  ENDIF.'),
 CODE('  IF p_test IS INITIAL.'),
 CODE('    lo_mgr->enqueue( <ls_sup>-partner ).'),
 CODE('    lo_mgr->apply_block( EXPORTING is_request = ls_req  IMPORTING ev_failed = lv_failed ).'),
 CODE('    lo_mgr->dequeue( <ls_sup>-partner ).'),
 CODE('  ENDIF.'),
 CODE('  lv_cnt = lv_cnt + 1.'),
 CODE('  IF lv_cnt MOD p_pack = 0.  COMMIT WORK AND WAIT.  ENDIF.'),
 CODE('ENDLOOP.'),
 H2('7.7 Output Layout'),
 P('Both the test run and the update run produce the same ALV list using CL_SALV_TABLE with layout /ZSUPBLK_STD. Traffic-light icons show the outcome per supplier and the summary line reports counts and runtime. The application log is reachable from the toolbar and from SLG1.'),
 ...figure('f09_log.png','ZMM_SUPBLK_MASS - result list with traffic lights and application log reference'),
 table(['Column','Field','Width','Notes'],[
  ['Icon','ICON','4','Green success, yellow warning, red error'],
  ['Supplier','LIFNR','10','Hotspot to transaction BP'],
  ['Name','NAME1','35',''],
  ['Company Code','BUKRS','4','Blank for central scope'],
  ['Purchasing Org.','EKORG','4','Blank for central scope'],
  ['Action','ACTION','8','Block or Unblock'],
  ['Reason','RSNCD','4','With text in the tooltip'],
  ['Message No.','MSGID / MSGNO','12',''],
  ['Message Text','MESSAGE','80','Fully substituted long text'],
 ],[1800,2000,1000,5280])
);

/* 8 BP behaviour */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('8. Effect on Standard Transactions'),
 H2('8.1 Business Partner Display'),
 P('After go-live the block fields in transaction BP become display-only for all roles except the emergency master data role. The custom attributes - reason code, validity and originating request - are shown in an additional group box so that a master data user can see why the supplier is blocked without leaving the transaction.'),
 ...figure('f04_bp.png','Transaction BP - block indicators and custom block attributes, display only'),
 H2('8.2 Downstream Transaction Behaviour'),
 table(['Transaction','Behaviour When Supplier Is Blocked','Message'],[
  ['ME51N / ME52N','Requisition can be created but the supplier cannot be entered as a fixed vendor.','06 619 hardened to error'],
  ['ME21N / ME22N','Purchase order creation and change are prevented for the affected purchasing organisation.','06 619 / ZSUPBLK 061'],
  ['ME59N','Automatic conversion of requisitions skips the supplier and reports it in the job log.','ZSUPBLK 062 (information)'],
  ['MIGO','Goods receipt against an existing order is permitted only when the blocked function is C (posting only).','ZSUPBLK 063 (warning)'],
  ['MIRO','Invoice can be posted but receives payment block R automatically.','ZSUPBLK 064 (information)'],
  ['F110','Payment run excludes the supplier through the standard payment block.','Standard FZ messages'],
  ['ME01 / source determination','Blocked supplier is excluded from source list determination and quota arrangement.','Standard 06 messages'],
 ],[1800,6280,2000]),
 H1('9. Non-Functional Requirements'),
 table(['Area','Requirement'],[
  ['Volume','Approximately 120 single requests per month; daily mass file of up to 400 suppliers; peak one-off run of 5,000 suppliers at cutover.'],
  ['Performance - dialog','Validation and impact preview must return within 3 seconds for 95% of requests. Master data update on final approval within 5 seconds.'],
  ['Performance - mass','5,000 suppliers must complete within 30 minutes in the update run. Package size 500 with COMMIT WORK AND WAIT.'],
  ['Locking','The business partner is locked for the shortest possible window around the update only, using ENQUEUE_EZBUPA. A lock conflict produces a retry after 2 seconds and a maximum of three attempts before the supplier is reported as failed.'],
  ['Availability','No specific availability requirement beyond the S/4HANA platform SLA. Mass runs must be schedulable outside the dialog window.'],
  ['Retention','Audit records retained for ten years; application log retained for two years then archived.'],
  ['Auditability','Every state change traceable to a user, timestamp, reason code and approval. No functional path exists that changes a block indicator without a log entry.'],
 ],[1700,8380]),
 H1('10. Security and Authorisation'),
 table(['Object / Field','Values','Assigned To'],[
  ['Z_SUPBLK ACTVT','01 create request, 02 block, 03 unblock, 21 ignore warnings, 03 display','01 to requesters, 02/03 to the application only via workflow, 21 to master data support'],
  ['Z_SUPBLK EKORG','Purchasing organisations the user may act on','Derived from the existing MM role'],
  ['Z_SUPBLK BUKRS','Company codes the user may act on','Derived from the existing FI role'],
  ['Z_SUPBLK ZRSNGRP','BC compliance, BQ quality, BF commercial, RL release','BC restricted to Compliance Officers only'],
  ['S_TCODE','ZMM_SUPBLK_MASS','Master data support role only'],
  ['Removed','Block field maintenance in BP / XK05 for all standard MM and FI roles','Security change request SEC-CR-4471'],
 ],[2300,4000,3780]),
 P('Segregation of duties is enforced in two places: the workflow agent rules exclude the requester (BR-04), and the update methods run under the workflow user rather than the dialog user, so that no dialog user can set a block indicator directly.')
);

/* 11 test */
children.push(new Paragraph({children:[new PageBreak()]}),
 H1('11. Test Scenarios'),
 table(['ID','Scenario','Expected Result'],[
  ['TC-01','Create central block, reason BQ03, both approvals given','LFA1-SPERR and SPERM set, BUT000-XBLCK set, status ACTIVE, log written'],
  ['TC-02','Create purchasing organisation block for EKORG 1000 only','LFM1-SPERM set for 1000 only; supplier remains transactable in EKORG 2000'],
  ['TC-03','Create block with reason BC01 (sanctions)','Scope forced to Central, valid-to disabled, step 1 skipped, Compliance approves within 24 h'],
  ['TC-04','Requester attempts to approve own request','ZSUPBLK 043 raised; work item routed to the deputy'],
  ['TC-05','Block a deletion-flagged supplier','ZSUPBLK 022 error; request cannot be submitted'],
  ['TC-06','Block a supplier with three open purchase orders','ZSUPBLK 011 warning shown and acknowledged; acknowledgement recorded in the log'],
  ['TC-07','Rejection at step 2','Status REJECTED, no master data change, requester notified'],
  ['TC-08','Unblock without an existing active block','ZSUPBLK 047 error'],
  ['TC-09','Unblock an active central block, reason RL02','All indicators cleared, original request set to RELEASED, event published'],
  ['TC-10','Mass test run over 500 suppliers','Full result list produced, no database change, return code reflects warnings'],
  ['TC-11','Mass update run with one failing supplier','Failing supplier reported red, remaining suppliers updated, return code 8'],
  ['TC-12','Lock conflict during mass run','Three retries then supplier reported as failed; no partial update'],
  ['TC-13','Valid-to date reached','Nightly job clears indicators, sets EXPIRED, notifies category manager'],
  ['TC-14','Pre-expiry notification','E-mail issued seven days before valid-to date'],
  ['TC-15','Purchase order creation for a blocked supplier','ME21N prevents the order with message 06 619 as an error'],
  ['TC-16','Invoice posting for a blocked supplier','MIRO posts with payment block R and message ZSUPBLK 064'],
  ['TC-17','Attempt to change block field directly in BP','Fields are display-only; no change possible'],
  ['TC-18','Authorisation failure on purchasing organisation','ZSUPBLK 041 error, request rejected before persistence'],
 ],[700,4200,5180]),
 H1('12. Open Items'),
 table(['ID','Open Item','Owner','Target Date'],[
  ['OI-01','Confirm whether payment block should also apply for reason group BQ*, or only for BC* and BF*','L. Trevino','29.08.2026'],
  ['OI-02','Agree the deputy list for category managers to satisfy BR-04 in all purchasing organisations','M. Okafor','05.09.2026'],
  ['OI-03','Decide the retention approach for GOS attachments beyond two years','Compliance / Basis','12.09.2026'],
  ['OI-04','Confirm the Ariba behaviour for suppliers blocked at purchasing organisation level only','Integration','12.09.2026'],
 ],[700,5900,1800,1680]),
 H1('Appendix A - Reason Code Catalogue'),
 table(['Code','Group','Description','Scope Forced','Valid-To Allowed','Approval'],[
  ['BC01','Compliance','Sanctions list match','Central','No','Compliance only'],
  ['BC02','Compliance','Adverse media / reputational risk','Central','No','Compliance only'],
  ['BC03','Compliance','Debarment by public authority','Central','No','Compliance only'],
  ['BC04','Compliance','Failed anti-bribery due diligence','Central','No','Compliance only'],
  ['BQ01','Quality','Failed supplier audit','Any','Yes','Category Manager + Compliance'],
  ['BQ02','Quality','Certification lapsed or withdrawn','Any','Yes','Category Manager + Compliance'],
  ['BQ03','Quality','Repeated quality non-conformance','Any','Yes','Category Manager + Compliance'],
  ['BF01','Commercial','Insolvency or administration','Central','Yes','Category Manager + Compliance'],
  ['BF02','Commercial','Contract terminated for cause','Any','Yes','Category Manager'],
  ['BF04','Commercial','Payment or credit risk','Any','Yes','Category Manager'],
  ['BL99','Legacy','Legacy block, reason not recorded','As migrated','Yes','Review required'],
  ['RL01','Release','Block period elapsed','n/a','n/a','Category Manager'],
  ['RL02','Release','Issue remediated and verified','n/a','n/a','Category Manager + Compliance'],
  ['RL03','Release','Blocked in error','n/a','n/a','Compliance'],
  ['RL04','Release','Sanctions match cleared as false positive','n/a','n/a','Compliance only'],
 ],[800,1400,3600,1400,1400,1480]),
 SP(),
 P('End of document.')
);

/* ---------- Build ---------- */
const doc=new Document({
 creator:'Procurement Solution Design',
 title:'FSD - Blocking and Unblocking of Registered Suppliers',
 numbering:{config:[
  {reference:'bul',levels:[{level:0,format:LevelFormat.BULLET,text:'•',alignment:AlignmentType.LEFT,
    style:{paragraph:{indent:{left:400,hanging:220}}}}]},
  {reference:'num',levels:[{level:0,format:LevelFormat.DECIMAL,text:'%1.',alignment:AlignmentType.LEFT,
    style:{paragraph:{indent:{left:400,hanging:220}}}}]}]},
 styles:{default:{
   document:{run:{font:'Calibri',size:20,color:'000000'}},
   heading1:{run:{font:'Calibri',size:28,bold:true,color:'1F3864'}},
   heading2:{run:{font:'Calibri',size:24,bold:true,color:'2E5C8A'}},
   heading3:{run:{font:'Calibri',size:21,bold:true,color:'44546A'}}}},
 sections:[{
  properties:{page:{size:{width:12240,height:15840},margin:{top:1080,bottom:1080,left:1080,right:1080}}},
  headers:{default:new Header({children:[new Paragraph({
    border:{bottom:{style:BorderStyle.SINGLE,size:6,color:'BFBFBF',space:4}},
    children:[new TextRun({text:'Functional Specification - Supplier Block / Unblock (MM-WA-014)',size:16,color:'595959'}),
      new TextRun({children:[new PositionalTab({alignment:PositionalTabAlignment.RIGHT,relativeTo:'margin',leader:PositionalTabLeader.NONE})],size:16}),
      new TextRun({text:'Version 1.0',size:16,color:'595959'})]})]})},
  footers:{default:new Footer({children:[new Paragraph({
    children:[new TextRun({text:'Confidential - internal use only',size:16,color:'595959'}),
      new TextRun({children:[new PositionalTab({alignment:PositionalTabAlignment.RIGHT,relativeTo:'margin',leader:PositionalTabLeader.NONE})],size:16}),
      new TextRun({children:['Page ',PageNumber.CURRENT,' of ',PageNumber.TOTAL_PAGES],size:16,color:'595959'})]})]})},
  children
 }]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(process.argv[2],b);console.log('written',b.length);});
