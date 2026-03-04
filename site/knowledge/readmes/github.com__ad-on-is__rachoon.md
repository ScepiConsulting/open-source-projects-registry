<div align="center">
<img src="https://raw.githubusercontent.com/ad-on-is/rachoon/main/apps/frontend/assets/logo.png" height="100" />
</div>

# Rachoon — The Clever Way to Handle Invoices

**Rachoon** (from _račun_, meaning _invoice_ in Bosnian) is a modern, self-hosted invoicing platform designed for freelancers, small
businesses, and everyone who wants full control over their billing. It helps you create and track invoices effortlessly — with the charm of its mascot, the ever-curious raccoon.

---

![Dashboard](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/dashboard.png)

---

## Features

✅ **Invoices & Offers** — Create and manage invoices and quotations in seconds.  
✅ **Client Management** — Keep all your client info organized and searchable.  
✅ **Payment Tracking** — Log payment status, view balances, and track overdue invoices.  
✅ **Custom Branding** — Highly customizable templates using nunjucks.  
✅ **Multi-Currency & Tax Support** — Bill globally with flexible tax and currency settings.  
✅ **PDF Export** — Instantly download professional-looking PDFs.  
✅ **Dashboard Insights** — Get a snapshot of your revenue, pending payments, and client stats.

---

## Screenshots

- [Invoice Management](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/invoices.png)
- [Invoice Creation](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/create-invoice.png)
- [Client Management](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/clients.png)
- [Settings](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/settings2.png)
- [Template Creation](https://raw.githubusercontent.com/ad-on-is/rachoon/main/.github/screenshots/template.png)

---

## 🦝 Why "Rachoon"?

The name comes from “račun”, which means invoice in Bosnian — combined with the word raccoon, because invoicing should be smart and quick.

---

## Tech Stack

- **Frontend:** Nuxt.js
- **Backend:** adonisJS
- **Database:** PostgreSQL
- **PDF Engine:** Gotenberg
- **Deployment:** Docker-ready, runs anywhere.

---

## Installation

```yaml
services:
  rachoon:
    image: ghcr.io/ad-on-is/rachoon
    container_name: rachoon
    environment:
      - APP_KEY=<some-app-key> # min 32 characters - used to encrypt and sign sensitive data
      - DB_CONNECTION=pg
      - GOTENBERG_URL=http://gotenberg:3000
      - PG_HOST=postgres16
      - PG_PORT=5432
      - PG_USER=<root-user>
      - PG_PASSWORD=<root-password>
      - PG_DB_NAME=rachoon
    ports:
      - 8080:8080

  gotenberg:
    image: gotenberg/gotenberg:8

  postgres16:
    container_name: postgres16
    image: postgres:16
    environment:
      - POSTGRES_USER=<root-user>
      - POSTGRES_PASSWORD=<root-password>
      - POSTGRES_DB=postgres
    volumes:
      - ./rachoon-data:/var/lib/postgresql/data
      - ./docker/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
```

## First steps

- Visit: <http://localhost:8080/signup>
- Create your account
- Start invoicing

---

## Development

This project uses a monorepo structure managed by Turborepo.

### Build Configuration

The project is organized with the following build outputs:

- **Frontend (Nuxt)**: `.output/` directory
- **Backend (AdonisJS)**: `build/` directory
- **Packages**: `dist/` directory

### Build Commands

```bash
# Install dependencies
pnpm install

# Build all packages
pnpm build

# Run in development mode
pnpm dev
```

### Project Structure

```text
rachoon/
├── apps/
│   ├── backend/     # AdonisJS API server
│   └── frontend/    # Nuxt.js web application
├── packages/
│   ├── common/      # Shared code
│   └── typescript-config/
└── turbo.json       # Turborepo configuration
```

### Testing

rachoon uses a comprehensive testing setup:

**backend tests (japa)**
```bash
cd apps/backend
pnpm test
```

**test structure**
- unit tests for models and services
- integration tests for api endpoints
- database seeding for test data

**ci/cd pipeline**

all pull requests and pushes trigger automated checks:
- code quality (linting, formatting)
- test execution with postgres test database
- build verification
- docker image creation (main branch only)

see [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed testing guidelines.

---

## Contributing

we welcome contributions! please read our [contribution guidelines](./CONTRIBUTING.md) to get started.

**quick start:**
1. fork the repository
2. create a feature branch
3. make your changes
4. add tests for new features
5. ensure all tests pass
6. submit a pull request

---

## License

see [LICENSE](./LICENSE) for details.
