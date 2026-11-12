//go:build !windows

package main

import (
	"errors"
	"os"
	"path/filepath"
)

func defaultDownloadDirectory() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, "Downloads", "M365-MCP"), nil
}

func protectData([]byte) ([]byte, error)   { return nil, errors.New("Windows DPAPI is required") }
func unprotectData([]byte) ([]byte, error) { return nil, errors.New("Windows DPAPI is required") }
func protectDirectory(string) error        { return errors.New("this application requires Windows") }
func lockState(string) (func(), error)     { return nil, errors.New("this application requires Windows") }
func openBrowser(string) error             { return errors.New("this application requires Windows") }
func attachWorkerLimits(int) (func(), error) {
	return nil, errors.New("Windows Job Objects are required for isolated extraction")
}
