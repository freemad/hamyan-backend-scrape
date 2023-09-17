# Hamyan Product Package

This is the code-base of all Hamyan products. Hamyan Product Family is a fintech solution in crowdsourcing and socio-financial credit, which helps people to uplift themselves financially and in-association with other individuals but in a complete independent manner.

It's been coded in Python (Django / DRF) from _October 2017_ until _July 2020_.

## The Technology Stack

The main tech stack which has been used in developing Hamyan Product Package is :
- Python (Django): for developing the main backend functionality.
- DRF (Django Rest Framework): which is used for serialising and exposing RESTful APIs as the main backend functionality.
- MySQL: as the DBMS to store data
- Celery Worker: to be used for some heavy-lifting tasks such as mass-SMS-send to subscribers, etc.
- Celery Beat: which is used for some periodical, cron-based-like tasks such as reminders, backup initiation, etc.
- Redis: which is used for an in-memory database for both Celery services and caching purposes.
- Docker/Docker Compose: which is used for containerising all modules in order to be deployed in some orchestration environment such as Docker Swarm or Kubernetes.

## Packages Description

The code contains the following modules and/or packages which will be discussed further next:

- General Modules
- Cashbox
- Moneypool
- Aptbox
- ROSCA

It also contains other utilities and helper files to assist staff and make the whole process more manageable.

Some of these utilities are:

- Scripts: which are used to handle tickets and/or some once-in-a-while tasks in the whole process
- Fixtures: which contains some base data to be used in DB reload
- MySQL: which is used to make periodical backups from the database for more security and integrity.
- Reports: which contains the periodical reports to the stakeholders/investors.
- and some more...


### General Modules

The general modules/packages are those which are used in all specific fintech modules/packages - the ones with specific fintech product functionality which make a fintech product family as a whole. These packages contain:

- Backend Engine: which is the glue of the whole product family that configures and wires all modules/packages together.
- Account Management: which its main functionality is management of the users, subscription, and their accounts is the whole product family.
- Analytics: which its purpose is to gather analytics and usage of the products' data to be used for business development and/or marketing.
- Hamyar: which is used to provide some marketing, user retention and inter-action for all the product family.
- Handshake: which its main purpose is to handshake and receive/provide services to other businesses in or out of the fintech ecosystem.
- Middleware: which is used as a very important role in intercepting and enriching API calls.
- Payment: one of the most important and actually the main engine of handling all sorts of financial transactions and various products financial services and balancing.
- Peripheral: used to handle all peripheral services in the fintech product family such as device management, etc. 
- Utils: handling all sorts of utility services such as announcements, randomisation, etc.
- Web:which provides the Template layer of the MVT architecture by using Django Template and JavaScript and such technologies like JQuery. 

### Cashbox

The CASHBOX is the first and foremost product of the whole Hamyan Product Family.

#### The Design

As the design aspect, Cashbox has a limited fixed member, share and time period, and all the members (shares/sub-shares) win in pre-defined or random order and obtain the fixed amount of prize.

But a Cashbox can have infinite rounds with different number of shares, share amounts and members.

### Moneypool

The most important product in Hamyan Product Family is MONEYPOOL.

#### The Design

A Moneypool is an unlimited gathering/delivering financial resources based on the number of shares and the shares' amounts which can vary through time and also the members.

Each member is contributing to the amount of money gathering in the Moneypool and then can borrow money from it via loans which will be returned and settled through installments (with/without interests).

### Aptbox

The third member of the Hamyan Product Family is APTBOX. It's used for managing the financial transactions and balancing in an apartment and its units.

#### The Design

All units (flats) in an apartment building has subscriptions in the Aptbox and pay their shares through the payment gateways in the application; the managing board of the apartment building then expends the stored amount in the chest for its services, and the reports are presented online and automatically in the app.

### ROSCA

The last member in the Hamyan Product Family is ROSCA box. It's an abbreviation of ROtating Savings and Credit Association.

#### The Design

A ROSCA is a special Cashbox with a single but an important difference; the seats are weighted and pre-assigned. Before the box round starts, the winners of all periods are defined and sold. The first seats get the sooner but lower prize, and gradually the prize goes higher as the box round comes to an end.
