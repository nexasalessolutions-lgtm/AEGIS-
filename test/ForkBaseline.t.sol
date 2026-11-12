// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Read-only baseline checks against a pinned local fork.
/// @dev This harness does not broadcast transactions or execute protocol actions.
interface Vm {
    function createSelectFork(string calldata rpcUrl, uint256 blockNumber) external returns (uint256);
    function envString(string calldata name) external returns (string memory);
    function envUint(string calldata name) external returns (uint256);
    function envAddress(string calldata name) external returns (address);
    function load(address target, bytes32 slot) external view returns (bytes32);
}

contract ForkBaseline {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    bytes32 internal constant IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    address internal target;
    uint256 internal pinnedBlock;

    function setUp() public {
        pinnedBlock = vm.envUint("FORK_BLOCK");
        vm.createSelectFork(vm.envString("RPC_URL"), pinnedBlock);
        target = vm.envAddress("TARGET");
    }

    function testForkUsesRequestedBlock() public view {
        require(block.number == pinnedBlock, "fork block mismatch");
    }

    function testTargetHasRuntimeCode() public view {
        require(target.code.length > 0, "target has no runtime code at pinned block");
    }

    function testEip1967ImplementationIfPresent() public view {
        bytes32 raw = vm.load(target, IMPLEMENTATION_SLOT);
        if (raw != bytes32(0)) {
            address implementation = address(uint160(uint256(raw)));
            require(implementation.code.length > 0, "implementation slot points to address without code");
        }
    }
}
