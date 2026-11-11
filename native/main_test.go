package main

import (
	"flag"
	"testing"
)

func TestLoginClientConfiguration(t *testing.T) {
	const projectClientID = "6e35216e-2623-43cc-b867-83bec0865cf3"
	const customClientID = "11111111-1111-1111-1111-111111111111"
	const tenantID = "22222222-2222-2222-2222-222222222222"
	tests := []struct {
		name       string
		clientEnv  string
		tenantEnv  string
		args       []string
		wantClient string
		wantTenant string
		wantError  bool
	}{
		{name: "built in", wantClient: projectClientID, wantTenant: "organizations"},
		{name: "environment", clientEnv: customClientID, tenantEnv: tenantID, wantClient: customClientID, wantTenant: tenantID},
		{name: "tenant only", tenantEnv: tenantID, wantClient: projectClientID, wantTenant: tenantID},
		{name: "command line", args: []string{"--client-id", customClientID, "--tenant", tenantID}, wantClient: customClientID, wantTenant: tenantID},
		{name: "flags override environment", clientEnv: "invalid", tenantEnv: "invalid", args: []string{"--client-id", customClientID, "--tenant", tenantID}, wantClient: customClientID, wantTenant: tenantID},
		{name: "mixed sources", clientEnv: customClientID, tenantEnv: "organizations", args: []string{"--tenant", tenantID}, wantClient: customClientID, wantTenant: tenantID},
		{name: "trim environment", clientEnv: " " + customClientID + "\n", tenantEnv: " " + tenantID + "\n", wantClient: customClientID, wantTenant: tenantID},
		{name: "blank environment", clientEnv: " \t", tenantEnv: " \t", wantClient: projectClientID, wantTenant: "organizations"},
		{name: "invalid environment stays invalid", clientEnv: "invalid", wantClient: "invalid", wantTenant: "organizations", wantError: true},
		{name: "explicit empty client stays invalid", clientEnv: customClientID, args: []string{"--client-id="}, wantClient: "", wantTenant: "organizations", wantError: true},
		{name: "invalid tenant stays invalid", tenantEnv: "https://evil.example", wantClient: projectClientID, wantTenant: "https://evil.example", wantError: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("M365_LOCAL_CLIENT_ID", tt.clientEnv)
			t.Setenv("M365_LOCAL_TENANT_ID", tt.tenantEnv)
			flags := flag.NewFlagSet("login", flag.ContinueOnError)
			config := loginFlags(flags)
			if err := flags.Parse(tt.args); err != nil {
				t.Fatal(err)
			}
			if config.ClientID != tt.wantClient || config.Tenant != tt.wantTenant {
				t.Fatalf("got client %q, tenant %q; want client %q, tenant %q", config.ClientID, config.Tenant, tt.wantClient, tt.wantTenant)
			}
			if err := config.validate(); (err != nil) != tt.wantError {
				t.Fatalf("unexpected validation result: %v", err)
			}
		})
	}
}
